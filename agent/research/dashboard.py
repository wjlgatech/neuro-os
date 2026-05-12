"""
Research-vertical dashboard (Lane 5).

A pure-aggregation rollup over the artifacts the other lanes write:

* ``registry.jsonl``         — drift events + ConstructiveExpression offers
* ``ingestion_runs.jsonl``   — Lane 1 audit log
* ``mechanism_cards/*.json`` — accepted cards (the primary metric)
* ``proposals/*/*.json``     — current queue snapshot

NEVER writes. Reading the dashboard is idempotent; it does not change
the trial state. Designed so the user can run it every morning to see
the compound curve before deciding whether the catalog is calibrating.

The implementation reads ``RESEARCH_CATALOG.underlying_needs`` (NOT a
hardcoded list) so when the catalog evolves, the "drift modes never
fired" signal evolves with it.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from agent.research.catalog import RESEARCH_CATALOG


# Days within which a same-mode re-fire counts as "the prior CE didn't stick".
# 7 days mirrors the design doc; tunable but not configurable from the CLI.
STICK_WINDOW_DAYS = 7


# Trend hysteresis: a 5% second-half/first-half change counts as a real
# trend; smaller deltas are reported as "flat" so daily noise doesn't
# flip the headline.
_TREND_UP_THRESHOLD = 1.05
_TREND_DOWN_THRESHOLD = 0.95


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class DashboardSummary(BaseModel):
    """One-shot rollup of the last N days for the research vertical.

    Pure function of (registry.jsonl + ingestion_runs.jsonl +
    mechanism_cards/*.json + proposals/*). Frozen — the dashboard is
    read-only; printing it is idempotent.
    """

    model_config = ConfigDict(frozen=True)

    vertical: Literal["research", "investment", "startup", "founder_loop"] = "research"
    window_days: int = Field(ge=1, le=365)
    generated_at: datetime

    # Compound-curve numbers (the headline).
    primary_metric_label: str = "mechanism cards/day"
    primary_metric_today: float = Field(ge=0.0)
    primary_metric_7d_avg: float = Field(ge=0.0)
    primary_metric_window_avg: float = Field(ge=0.0)
    primary_metric_window_trend: Literal["up", "down", "flat"] = "flat"

    # Drift-mode usage histogram.
    drift_mode_counts: Dict[str, int] = Field(default_factory=dict)
    drift_mode_top_3: List[Tuple[str, int]] = Field(default_factory=list, max_length=3)

    # Constructive-expression stick-rate. "Accepted" mirrors "offered" today
    # (every propose op is an implicit offer; an explicit user-accept signal
    # arrives with the chat surface). "Stuck" is the differentiating signal:
    # offered AND no same-mode re-fire with a different primary_action within
    # STICK_WINDOW_DAYS.
    constructive_expressions_offered: int = Field(ge=0)
    constructive_expressions_accepted: int = Field(ge=0)
    constructive_expressions_stuck: int = Field(ge=0)

    # Lane 1 ingestion health.
    sources_scanned: int = Field(ge=0)
    proposals_emitted: int = Field(ge=0)
    proposals_accepted: int = Field(ge=0)
    proposals_rejected: int = Field(ge=0)

    # Catalog-revision evidence: drift modes the catalog claims exist but
    # that NEVER fired in the window.
    drift_modes_never_fired: List[str] = Field(default_factory=list)

    # Action queue (so the dashboard footer is actionable).
    pending_proposals_count: int = Field(ge=0)
    pending_proposals_oldest_age_hours: Optional[float] = None

    # Three-Layer Research OS signals — anti-survey-mode counters.
    tier_balance: Dict[str, int] = Field(
        default_factory=dict,
        description="Counts of accepted MechanismCards by RawSource.tier "
                    "(seed / frontier / lateral / unknown). A heavy "
                    "frontier-only ratio flags 'chaser_mode'.",
    )
    verdict_histogram: Dict[str, int] = Field(
        default_factory=dict,
        description="Counts of accepted MechanismCards by `verdict` "
                    "(foundational / useful / misleading / skip / "
                    "unrated). Zero skips + zero misleading on a "
                    "large-enough sample flags 'rubber_stamping'.",
    )

    # Layer-2 / Layer-3 / checkpoint progress.
    synthesis_run_count: int = Field(ge=0, default=0)
    synthesis_latest_cluster_count: Optional[int] = None
    briefs_produced_in_window: int = Field(ge=0, default=0)
    latest_checkpoint_converging: Optional[bool] = None
    checkpoint_no_streak: int = Field(ge=0, default=0)

    # Aggregated health verdict. Each flag is "fired" iff its observable
    # evidence is unambiguous; never fires on small samples.
    system_health_flags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------


def _research_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_research")


def _read_jsonl(path: Path) -> List[dict]:
    """Stream-read a JSONL file. Missing file → []. Malformed lines skipped."""
    if not path.exists():
        return []
    rows: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _parse_ts(raw: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp; tolerate missing or malformed values."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


# ---------------------------------------------------------------------------
# Aggregation primitives (each independently testable).
# ---------------------------------------------------------------------------


def _filter_window(
    rows: List[dict],
    *,
    now: datetime,
    window_days: int,
) -> List[dict]:
    """Keep rows whose ``ts`` is within ``now - window_days`` (inclusive)."""
    cutoff = now - timedelta(days=window_days)
    out: List[dict] = []
    for r in rows:
        ts = _parse_ts(r.get("ts"))
        if ts is None:
            continue
        if ts >= cutoff:
            out.append(r)
    return out


def _aggregate_drift_modes(rows: List[dict]) -> Dict[str, int]:
    """Bucket ``propose_constructive_expression`` ops by their underlying need."""
    counts: Dict[str, int] = {}
    for r in rows:
        action = r.get("action") or {}
        if action.get("op") != "propose_constructive_expression":
            continue
        diagnosis = action.get("diagnosis") or {}
        need = diagnosis.get("underlying_need")
        if not isinstance(need, str):
            continue
        counts[need] = counts.get(need, 0) + 1
    return counts


def _compute_stick_rate(rows: List[dict]) -> Tuple[int, int, int]:
    """Returns (offered, accepted, stuck).

    Today ``accepted == offered`` (no explicit accept signal yet —
    that arrives with the chat surface). ``stuck`` is the load-bearing
    signal: a propose op is "stuck" iff the same drift mode does NOT
    re-fire within STICK_WINDOW_DAYS with a different primary_action.
    """
    proposes: List[Tuple[datetime, str, str]] = []  # (ts, mode, primary_action)
    for r in rows:
        action = r.get("action") or {}
        if action.get("op") != "propose_constructive_expression":
            continue
        ts = _parse_ts(r.get("ts"))
        diagnosis = action.get("diagnosis") or {}
        need = diagnosis.get("underlying_need")
        payload = action.get("payload") or {}
        primary = payload.get("primary_action")
        if ts is None or not isinstance(need, str) or not isinstance(primary, str):
            continue
        proposes.append((ts, need, primary))

    offered = len(proposes)
    if offered == 0:
        return (0, 0, 0)

    proposes.sort(key=lambda x: x[0])
    stuck = 0
    for i, (ts_i, mode_i, action_i) in enumerate(proposes):
        cutoff = ts_i + timedelta(days=STICK_WINDOW_DAYS)
        overridden = False
        for ts_j, mode_j, action_j in proposes[i + 1 :]:
            if ts_j > cutoff:
                break
            if mode_j == mode_i and action_j != action_i:
                overridden = True
                break
        if not overridden:
            stuck += 1
    return (offered, offered, stuck)


def _aggregate_proposals(home: Optional[Path]) -> Tuple[int, int, int]:
    """Returns (pending_count, accepted_count, rejected_count)."""
    base = _research_home(home) / "proposals"
    counts = []
    for status in ("pending", "accepted", "rejected"):
        d = base / status
        n = sum(1 for p in d.glob("*.json") if p.is_file()) if d.exists() else 0
        counts.append(n)
    return tuple(counts)  # type: ignore[return-value]


def _aggregate_ingestion(
    home: Optional[Path],
    *,
    now: datetime,
    window_days: int,
) -> Tuple[int, int]:
    """Sum (sources_scanned, proposals_emitted) over runs in the window."""
    rows = _read_jsonl(_research_home(home) / "ingestion_runs.jsonl")
    cutoff = now - timedelta(days=window_days)
    sources = 0
    proposals = 0
    for r in rows:
        started = _parse_ts(r.get("started_at"))
        if started is None or started < cutoff:
            continue
        try:
            sources += int(r.get("sources_scanned") or 0)
            proposals += int(r.get("proposals_emitted") or 0)
        except (TypeError, ValueError):
            continue
    return (sources, proposals)


def _bucket_cards_by_day(home: Optional[Path]) -> Dict[str, int]:
    """Read ``mechanism_cards/*.json``, bucket by ISO date of the card's ``ts``."""
    cards_dir = _research_home(home) / "mechanism_cards"
    out: Dict[str, int] = {}
    if not cards_dir.exists():
        return out
    for p in cards_dir.glob("*.json"):
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = _parse_ts(body.get("ts"))
        if ts is None:
            continue
        key = ts.date().isoformat()
        out[key] = out.get(key, 0) + 1
    return out


def _compute_primary_metric(
    home: Optional[Path],
    *,
    now: datetime,
    window_days: int,
) -> Tuple[float, float, float, Literal["up", "down", "flat"]]:
    """Returns (today, 7d_avg, window_avg, trend)."""
    by_day = _bucket_cards_by_day(home)
    today_key = now.date().isoformat()
    today = float(by_day.get(today_key, 0))

    def _avg_over(days: int) -> float:
        if days <= 0:
            return 0.0
        total = 0
        for offset in range(days):
            d = (now - timedelta(days=offset)).date().isoformat()
            total += by_day.get(d, 0)
        return total / days

    avg_7d = _avg_over(min(7, window_days))
    avg_window = _avg_over(window_days)

    trend: Literal["up", "down", "flat"] = "flat"
    half = window_days // 2
    if half >= 1:
        first_half = 0
        second_half = 0
        for offset in range(window_days):
            d = (now - timedelta(days=offset)).date().isoformat()
            n = by_day.get(d, 0)
            # offsets [0..half) are the most recent half (second half of the
            # window in chronological order); offsets [half..window) are older.
            if offset < half:
                second_half += n
            else:
                first_half += n
        first_avg = first_half / max(window_days - half, 1)
        second_avg = second_half / max(half, 1)
        if first_avg == 0:
            trend = "up" if second_avg > 0 else "flat"
        elif second_avg > first_avg * _TREND_UP_THRESHOLD:
            trend = "up"
        elif second_avg < first_avg * _TREND_DOWN_THRESHOLD:
            trend = "down"
        else:
            trend = "flat"
    return (today, avg_7d, avg_window, trend)


# ---------------------------------------------------------------------------
# Layer-1 deepening signals: tier balance + verdict histogram
# ---------------------------------------------------------------------------


def _iter_cards_in_window(
    home: Optional[Path],
    *,
    now: datetime,
    window_days: int,
) -> List[dict]:
    """Read mechanism_cards/*.json and return those whose ts is within
    the window. Plain dicts (not models) to keep this read-only and
    decoupled from MechanismCard's domain dependencies."""
    cards_dir = _research_home(home) / "mechanism_cards"
    if not cards_dir.exists():
        return []
    cutoff = now - timedelta(days=window_days)
    out: List[dict] = []
    for p in cards_dir.glob("*.json"):
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = _parse_ts(body.get("ts"))
        if ts is None or ts < cutoff:
            continue
        out.append(body)
    return out


def _aggregate_tier_balance(
    home: Optional[Path],
    *,
    now: datetime,
    window_days: int,
) -> Dict[str, int]:
    """Bucket accepted proposals (and any tier-tagged MechanismCard) by
    source_tier. Cards without a tier accumulate under 'unknown'."""
    # Proposals carry source_tier (mirrored from the originating
    # RawSource). MechanismCards do not — we only have the RAW source
    # tier on the proposal side. Read the accepted proposals dir.
    counts: Dict[str, int] = {}
    proposals_dir = _research_home(home) / "proposals" / "accepted"
    if proposals_dir.exists():
        cutoff = now - timedelta(days=window_days)
        for p in proposals_dir.glob("*.json"):
            try:
                body = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            ts = _parse_ts(body.get("proposed_at"))
            if ts is None or ts < cutoff:
                continue
            tier = body.get("source_tier") or "unknown"
            if not isinstance(tier, str):
                tier = "unknown"
            counts[tier] = counts.get(tier, 0) + 1
    return counts


def _aggregate_verdict_histogram(
    cards: List[dict],
) -> Dict[str, int]:
    """Bucket accepted MechanismCards by verdict. Cards without a verdict
    field bucket under 'unrated'."""
    counts: Dict[str, int] = {}
    for c in cards:
        v = c.get("verdict") or "unrated"
        if not isinstance(v, str):
            v = "unrated"
        counts[v] = counts.get(v, 0) + 1
    return counts


def _count_synthesis_runs(
    home: Optional[Path],
    *,
    now: datetime,
    window_days: int,
) -> Tuple[int, Optional[int]]:
    """Return (run_count_in_window, latest_cluster_count_in_window).
    Latest is None when no runs in window."""
    runs_dir = _research_home(home) / "synthesis" / "runs"
    if not runs_dir.exists():
        return (0, None)
    cutoff = now - timedelta(days=window_days)
    runs: List[Tuple[datetime, int]] = []
    for p in runs_dir.glob("*.json"):
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = _parse_ts(body.get("generated_at"))
        if ts is None or ts < cutoff:
            continue
        clusters = body.get("clusters")
        cluster_count = len(clusters) if isinstance(clusters, list) else 0
        runs.append((ts, cluster_count))
    if not runs:
        return (0, None)
    runs.sort(key=lambda r: r[0])
    return (len(runs), runs[-1][1])


def _count_briefs_in_window(
    home: Optional[Path],
    *,
    now: datetime,
    window_days: int,
) -> int:
    briefs_dir = _research_home(home) / "briefs"
    if not briefs_dir.exists():
        return 0
    cutoff = now - timedelta(days=window_days)
    n = 0
    for p in briefs_dir.glob("*.json"):
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = _parse_ts(body.get("generated_at"))
        if ts is None or ts < cutoff:
            continue
        n += 1
    return n


def _compute_health_flags(
    *,
    tier_balance: Dict[str, int],
    verdict_histogram: Dict[str, int],
    proposals_accepted: int,
    oldest_pending_age_hours: Optional[float],
    briefs_produced: int,
    checkpoint_no_streak: int,
) -> List[str]:
    """Compute the dashboard's health flags. Each flag fires ONLY when
    the evidence is unambiguous; sample-size guards make small-corpus
    days flag-free.

    Flags:
      * chaser_mode      — ≥5 accepted, >70% frontier, <10% seed
      * hoarder_mode     — oldest pending age > 14 days (the inbox rule)
      * rubber_stamping  — ≥5 rated, zero skip + zero misleading
      * no_synthesis     — ≥5 accepted but zero briefs in window
      * system_not_converging — ≥2 consecutive non-converging checkpoints
    """
    flags: List[str] = []
    tier_total = sum(tier_balance.values())
    if tier_total >= 5:
        frontier = tier_balance.get("frontier", 0)
        seed = tier_balance.get("seed", 0)
        if frontier / tier_total > 0.70 and seed / tier_total < 0.10:
            flags.append("chaser_mode")

    if (
        oldest_pending_age_hours is not None
        and oldest_pending_age_hours > 14 * 24
    ):
        flags.append("hoarder_mode")

    rated = sum(
        v for k, v in verdict_histogram.items()
        if k in ("foundational", "useful", "misleading", "skip")
    )
    if rated >= 5:
        skip_or_misleading = (
            verdict_histogram.get("skip", 0)
            + verdict_histogram.get("misleading", 0)
        )
        if skip_or_misleading == 0:
            flags.append("rubber_stamping")

    if proposals_accepted >= 5 and briefs_produced == 0:
        flags.append("no_synthesis")

    # 2 consecutive non-converging checkpoints — uses CONVERGENCE_WARNING_THRESHOLD.
    from agent.research.checkpoints import CONVERGENCE_WARNING_THRESHOLD
    if checkpoint_no_streak >= CONVERGENCE_WARNING_THRESHOLD:
        flags.append("system_not_converging")

    return flags


def _compute_oldest_pending_age_hours(
    home: Optional[Path],
    *,
    now: datetime,
) -> Optional[float]:
    """Return age (hours) of the OLDEST pending proposal; None if none."""
    pending_dir = _research_home(home) / "proposals" / "pending"
    if not pending_dir.exists():
        return None
    oldest: Optional[datetime] = None
    for p in pending_dir.glob("*.json"):
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = _parse_ts(body.get("proposed_at"))
        if ts is None:
            continue
        if oldest is None or ts < oldest:
            oldest = ts
    if oldest is None:
        return None
    delta = now - oldest
    return max(delta.total_seconds() / 3600.0, 0.0)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_dashboard_summary(
    *,
    home: Optional[Path] = None,
    window_days: int = 40,
    now: Optional[datetime] = None,
) -> DashboardSummary:
    """Build the rollup. Reads only; writes nothing."""
    when = now or datetime.now(timezone.utc)

    registry_rows = _read_jsonl(_research_home(home) / "registry.jsonl")
    window_rows = _filter_window(registry_rows, now=when, window_days=window_days)

    drift_counts = _aggregate_drift_modes(window_rows)
    drift_top_3 = sorted(drift_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    fired = set(drift_counts.keys())
    never_fired = [m for m in RESEARCH_CATALOG.underlying_needs if m not in fired]

    offered, accepted, stuck = _compute_stick_rate(window_rows)
    pending, accepted_files, rejected_files = _aggregate_proposals(home)
    sources, emitted = _aggregate_ingestion(home, now=when, window_days=window_days)
    today, avg7, avg_w, trend = _compute_primary_metric(
        home, now=when, window_days=window_days
    )
    oldest_age = _compute_oldest_pending_age_hours(home, now=when)

    # Three-Layer Research OS signals.
    cards_in_window = _iter_cards_in_window(home, now=when, window_days=window_days)
    tier_balance = _aggregate_tier_balance(home, now=when, window_days=window_days)
    verdict_hist = _aggregate_verdict_histogram(cards_in_window)
    synthesis_count, synthesis_latest_clusters = _count_synthesis_runs(
        home, now=when, window_days=window_days,
    )
    briefs_n = _count_briefs_in_window(home, now=when, window_days=window_days)

    # Checkpoints: read latest streak + most-recent converging flag.
    from agent.research.checkpoints import latest_checkpoint, recent_no_streak
    no_streak = recent_no_streak(home=home, k=10)
    latest = latest_checkpoint(home=home)
    latest_converging: Optional[bool] = None
    if latest is not None:
        latest_converging = bool(latest.brief_produced and latest.mental_model_clearer)

    flags = _compute_health_flags(
        tier_balance=tier_balance,
        verdict_histogram=verdict_hist,
        proposals_accepted=accepted_files,
        oldest_pending_age_hours=oldest_age,
        briefs_produced=briefs_n,
        checkpoint_no_streak=no_streak,
    )

    return DashboardSummary(
        vertical="research",
        window_days=window_days,
        generated_at=when,
        primary_metric_today=today,
        primary_metric_7d_avg=avg7,
        primary_metric_window_avg=avg_w,
        primary_metric_window_trend=trend,
        drift_mode_counts=drift_counts,
        drift_mode_top_3=drift_top_3,
        constructive_expressions_offered=offered,
        constructive_expressions_accepted=accepted,
        constructive_expressions_stuck=stuck,
        sources_scanned=sources,
        proposals_emitted=emitted,
        proposals_accepted=accepted_files,
        proposals_rejected=rejected_files,
        drift_modes_never_fired=never_fired,
        pending_proposals_count=pending,
        pending_proposals_oldest_age_hours=oldest_age,
        tier_balance=tier_balance,
        verdict_histogram=verdict_hist,
        synthesis_run_count=synthesis_count,
        synthesis_latest_cluster_count=synthesis_latest_clusters,
        briefs_produced_in_window=briefs_n,
        latest_checkpoint_converging=latest_converging,
        checkpoint_no_streak=no_streak,
        system_health_flags=flags,
    )


# ---------------------------------------------------------------------------
# Renderer (text output)
# ---------------------------------------------------------------------------


def render_text(summary: DashboardSummary) -> str:
    """Render the summary as ~30 lines of plain text."""
    lines: List[str] = []
    when = summary.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append(
        f"research vertical — {summary.window_days}-day dashboard (generated {when})"
    )
    lines.append("=" * 70)
    lines.append("")

    lines.append("Compound curve")
    lines.append(
        f"  {summary.primary_metric_label:24s}"
        f"  today={summary.primary_metric_today:.1f}"
        f"   7d-avg={summary.primary_metric_7d_avg:.2f}"
        f"   {summary.window_days}d-avg={summary.primary_metric_window_avg:.2f}"
        f"   trend={summary.primary_metric_window_trend}"
    )
    lines.append("")

    lines.append(f"Drift-mode usage (top {min(3, len(summary.drift_mode_top_3))})")
    if summary.drift_mode_top_3:
        max_count = max(c for _, c in summary.drift_mode_top_3) or 1
        for mode, count in summary.drift_mode_top_3:
            bar = "█" * max(int((count / max_count) * 24), 1)
            lines.append(f"  {mode:22s} {bar}  {count}")
    else:
        lines.append("  (no drift events in window)")
    if summary.drift_modes_never_fired:
        names = " / ".join(summary.drift_modes_never_fired)
        lines.append(f"  ({names} fired 0 times — catalog candidates?)")
    lines.append("")

    lines.append("Constructive expressions")
    if summary.constructive_expressions_offered:
        rate = (
            summary.constructive_expressions_stuck
            / summary.constructive_expressions_offered
        ) * 100
        lines.append(
            f"  offered:  {summary.constructive_expressions_offered}"
            f"   accepted:  {summary.constructive_expressions_accepted}"
            f"   stuck:  {summary.constructive_expressions_stuck}"
            f"   stick-rate={rate:.0f}%"
        )
    else:
        lines.append("  (no constructive expressions offered in window)")
    lines.append("")

    lines.append("Lane 1 ingestion")
    lines.append(
        f"  sources scanned:    {summary.sources_scanned}"
        f"     proposals emitted:  {summary.proposals_emitted}"
    )
    lines.append(
        f"  accepted:           {summary.proposals_accepted}"
        f"     rejected:           {summary.proposals_rejected}"
        f"     pending:  {summary.pending_proposals_count}"
    )
    lines.append("")

    lines.append("Action queue")
    if summary.pending_proposals_count == 0:
        lines.append("  (no pending proposals)")
    else:
        age = summary.pending_proposals_oldest_age_hours
        age_str = f"{age:.0f}h old" if age is not None else "age unknown"
        plural = "s" if summary.pending_proposals_count != 1 else ""
        lines.append(
            f"  {summary.pending_proposals_count} pending proposal{plural}"
            f" — oldest {age_str}.  Run `research review --cli`."
        )
    lines.append("")

    # Three-Layer Research OS signals.
    lines.append("Three-Layer Research OS")
    tier_total = sum(summary.tier_balance.values())
    if tier_total:
        parts = [f"{k}={v}" for k, v in sorted(summary.tier_balance.items())]
        lines.append(f"  tier balance:        {'  '.join(parts)}")
    else:
        lines.append("  tier balance:        (no accepted proposals in window)")
    verdict_total = sum(summary.verdict_histogram.values())
    if verdict_total:
        parts = [
            f"{k}={v}"
            for k, v in sorted(summary.verdict_histogram.items(), key=lambda kv: -kv[1])
        ]
        lines.append(f"  verdicts:            {'  '.join(parts)}")
    else:
        lines.append("  verdicts:            (no accepted MechanismCards in window)")
    lines.append(
        f"  synthesis runs:      {summary.synthesis_run_count}"
        + (
            f"   latest cluster count: {summary.synthesis_latest_cluster_count}"
            if summary.synthesis_latest_cluster_count is not None
            else ""
        )
    )
    lines.append(f"  briefs in window:    {summary.briefs_produced_in_window}")
    if summary.latest_checkpoint_converging is not None:
        verdict = "converging" if summary.latest_checkpoint_converging else "NOT converging"
        lines.append(
            f"  latest checkpoint:   {verdict}"
            f"   trailing non-converging streak: {summary.checkpoint_no_streak}"
        )
    else:
        lines.append("  latest checkpoint:   (none — run `research checkpoint`)")
    if summary.system_health_flags:
        lines.append(f"  health flags:        {', '.join(summary.system_health_flags)}")
    else:
        lines.append("  health flags:        (none)")
    lines.append("")

    return "\n".join(lines)


__all__ = [
    "STICK_WINDOW_DAYS",
    "DashboardSummary",
    "build_dashboard_summary",
    "render_text",
]
