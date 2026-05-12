"""
Investment-vertical dashboard (advisory-only).

A pure-aggregation rollup over the artifacts the other modules write:

* ``cost_of_living.json``         — headline target
* ``trades/*.json``               — TradeLog journal (premium, max-loss, win-prob)
* ``position_theses/*.json``      — PositionThesis with optional sleeve tag
* ``calibration_records/*.json``  — calibration trail
* ``bias_checks/*.json``          — belief_os bias-check audit

NEVER writes. Reading the dashboard is idempotent.

The user runs ``invest dashboard --window 30`` weekly to see:
  - Premium run-rate vs. monthly cost-of-living target (the headline)
  - Trade-log composition by strategy + sleeve
  - Max-loss exposure (the discipline gate)
  - Calibration error trend
  - Bias-check pulse

Mirrors the research-dashboard pattern (``agent/research/dashboard.py``).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from agent.investment.cost_of_living import read_cost_of_living_target
from agent.investment.trade import iter_trade_logs


# Map confidence → 0..1 score for calibration error (mirrors config.py:nightly).
_CONF_TO_SCORE = {"low": 0.25, "medium": 0.5, "high": 0.85}


def _investment_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_investment")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class InvestDashboardSummary(BaseModel):
    """Frozen rollup of the last N days for the investment vertical.

    Pure function of (cost_of_living.json + trades/*.json +
    position_theses/*.json + calibration_records/*.json +
    bias_checks/*.json).
    """

    model_config = ConfigDict(frozen=True)

    vertical: Literal["investment"] = "investment"
    window_days: int = Field(ge=1, le=365)
    generated_at: datetime

    # Headline — cost-of-living coverage
    monthly_target: Optional[float] = Field(default=None, ge=0.0)
    region: Optional[str] = None
    premium_collected_in_window: float = Field(ge=0.0, default=0.0)
    premium_per_month_run_rate: float = Field(ge=0.0, default=0.0)
    cost_of_living_coverage_pct: Optional[float] = None

    # Trade-log rollup
    trades_in_window: int = Field(ge=0, default=0)
    trades_by_strategy: Dict[str, int] = Field(default_factory=dict)
    max_loss_exposure_total: float = Field(ge=0.0, default=0.0)
    mean_win_prob: Optional[float] = None
    mean_assignment_prob: Optional[float] = None

    # Sleeve allocation (across all ACTIVE theses, not windowed)
    theses_by_sleeve: Dict[str, int] = Field(default_factory=dict)

    # Calibration + bias (mirrors config.py:nightly, windowed)
    calibration_error_in_window: Optional[float] = None
    bias_checks_in_window: int = Field(ge=0, default=0)


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------


def _parse_ts(raw: Optional[str]) -> Optional[datetime]:
    if not raw or not isinstance(raw, str):
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _iter_jsons_in_window(
    base: Path,
    *,
    ts_field: str,
    now: datetime,
    window_days: int,
) -> List[dict]:
    """Read every ``*.json`` in ``base``, parse, filter by timestamp window.
    Malformed files are skipped silently — the dashboard must not crash
    on a single bad row."""
    if not base.exists():
        return []
    cutoff = now - timedelta(days=window_days)
    out: List[dict] = []
    for p in base.glob("*.json"):
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = _parse_ts(body.get(ts_field))
        if ts is None or ts < cutoff:
            continue
        out.append(body)
    return out


# ---------------------------------------------------------------------------
# Aggregation primitives (each independently testable)
# ---------------------------------------------------------------------------


def _aggregate_trade_rollup(
    *,
    home: Optional[Path],
    now: datetime,
    window_days: int,
) -> Dict[str, object]:
    """Returns a dict with: count, premium_sum, max_loss_sum, by_strategy,
    mean_win_prob, mean_assignment_prob.
    """
    trades = list(iter_trade_logs(home=home, window_days=window_days, now=now))
    if not trades:
        return {
            "count": 0,
            "premium_sum": 0.0,
            "max_loss_sum": 0.0,
            "by_strategy": {},
            "mean_win_prob": None,
            "mean_assignment_prob": None,
        }
    by_strategy: Dict[str, int] = {}
    for t in trades:
        by_strategy[t.strategy] = by_strategy.get(t.strategy, 0) + 1
    return {
        "count": len(trades),
        "premium_sum": sum(t.premium for t in trades),
        "max_loss_sum": sum(t.max_loss for t in trades),
        "by_strategy": by_strategy,
        "mean_win_prob": sum(t.win_prob for t in trades) / len(trades),
        "mean_assignment_prob": sum(t.assignment_prob for t in trades) / len(trades),
    }


def _aggregate_sleeve_allocation(
    *,
    home: Optional[Path],
) -> Dict[str, int]:
    """Count ACTIVE theses by sleeve. None → "untagged".

    Reads the raw JSON (not the Pydantic model) so older files that
    don't yet have a ``sleeve`` field bucket gracefully under
    "untagged" without requiring a re-parse.
    """
    theses_dir = _investment_home(home) / "position_theses"
    counts: Dict[str, int] = {}
    if not theses_dir.exists():
        return counts
    for p in theses_dir.glob("*.json"):
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if body.get("status", "active") != "active":
            continue
        sleeve = body.get("sleeve") or "untagged"
        if not isinstance(sleeve, str):
            sleeve = "untagged"
        counts[sleeve] = counts.get(sleeve, 0) + 1
    return counts


def _aggregate_calibration_error(
    *,
    home: Optional[Path],
    now: datetime,
    window_days: int,
) -> Optional[float]:
    """Compute mean |confidence_score - actual_outcome| over records
    whose ``ts`` is within the window. None when the window is empty.
    """
    base = _investment_home(home) / "calibration_records"
    rows = _iter_jsons_in_window(
        base, ts_field="ts", now=now, window_days=window_days
    )
    if not rows:
        return None
    errors = []
    for rec in rows:
        pred = _CONF_TO_SCORE.get(rec.get("predicted_confidence", ""), 0.5)
        actual = 1.0 if rec.get("thesis_still_valid") else 0.0
        errors.append(abs(pred - actual))
    return sum(errors) / len(errors)


def _count_bias_checks_in_window(
    *,
    home: Optional[Path],
    now: datetime,
    window_days: int,
) -> int:
    base = _investment_home(home) / "bias_checks"
    rows = _iter_jsons_in_window(
        base, ts_field="ts", now=now, window_days=window_days
    )
    return len(rows)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_invest_dashboard(
    *,
    home: Optional[Path] = None,
    window_days: int = 30,
    now: Optional[datetime] = None,
) -> InvestDashboardSummary:
    """Build the rollup. Reads only; writes nothing."""
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    target = read_cost_of_living_target(home=home)
    monthly_target = target.monthly_target if target is not None else None
    region = target.region if target is not None else None

    trade_roll = _aggregate_trade_rollup(
        home=home, now=when, window_days=window_days
    )
    premium_sum = float(trade_roll["premium_sum"])
    run_rate = premium_sum * 30.0 / window_days
    coverage_pct: Optional[float] = None
    if monthly_target and monthly_target > 0:
        coverage_pct = run_rate / monthly_target

    sleeves = _aggregate_sleeve_allocation(home=home)
    cal_err = _aggregate_calibration_error(
        home=home, now=when, window_days=window_days
    )
    bias_n = _count_bias_checks_in_window(
        home=home, now=when, window_days=window_days
    )

    return InvestDashboardSummary(
        window_days=window_days,
        generated_at=when,
        monthly_target=monthly_target,
        region=region,
        premium_collected_in_window=premium_sum,
        premium_per_month_run_rate=run_rate,
        cost_of_living_coverage_pct=coverage_pct,
        trades_in_window=int(trade_roll["count"]),
        trades_by_strategy=dict(trade_roll["by_strategy"]),  # type: ignore[arg-type]
        max_loss_exposure_total=float(trade_roll["max_loss_sum"]),
        mean_win_prob=trade_roll["mean_win_prob"],  # type: ignore[arg-type]
        mean_assignment_prob=trade_roll["mean_assignment_prob"],  # type: ignore[arg-type]
        theses_by_sleeve=sleeves,
        calibration_error_in_window=cal_err,
        bias_checks_in_window=bias_n,
    )


# ---------------------------------------------------------------------------
# Renderer (text output)
# ---------------------------------------------------------------------------


def render_text(summary: InvestDashboardSummary) -> str:
    """Render the summary as ~25 lines of plain text."""
    lines: List[str] = []
    when = summary.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append(
        f"investment vertical — {summary.window_days}-day dashboard "
        f"(generated {when})"
    )
    lines.append("=" * 70)
    lines.append("")

    # Headline
    lines.append("Cost-of-living coverage")
    if summary.monthly_target is not None:
        lines.append(
            f"  monthly target:      ${summary.monthly_target:,.0f}"
            f"  ({summary.region or '?'})"
        )
    else:
        lines.append(
            "  monthly target:      (unset — run "
            "`invest cost-of-living set`)"
        )
    lines.append(
        f"  premium ({summary.window_days}d):       "
        f"${summary.premium_collected_in_window:,.0f}"
    )
    lines.append(
        f"  monthly run-rate:    "
        f"${summary.premium_per_month_run_rate:,.0f}"
    )
    if summary.cost_of_living_coverage_pct is not None:
        pct = summary.cost_of_living_coverage_pct * 100
        lines.append(f"  coverage:            {pct:.0f}%")
    else:
        lines.append("  coverage:            (no target set)")
    lines.append("")

    # Trades
    lines.append("Trade journal")
    lines.append(
        f"  trades in window:    {summary.trades_in_window}"
        f"     max-loss exposure: ${summary.max_loss_exposure_total:,.0f}"
    )
    if summary.trades_by_strategy:
        parts = [
            f"{k}={v}"
            for k, v in sorted(
                summary.trades_by_strategy.items(),
                key=lambda kv: -kv[1],
            )
        ]
        lines.append(f"  by strategy:         {'  '.join(parts)}")
    else:
        lines.append("  by strategy:         (no trades in window)")
    if summary.mean_win_prob is not None:
        lines.append(
            f"  mean win-prob:       {summary.mean_win_prob:.2f}"
            f"     mean assignment-prob: "
            f"{summary.mean_assignment_prob:.2f}"
            if summary.mean_assignment_prob is not None
            else f"  mean win-prob:       {summary.mean_win_prob:.2f}"
        )
    lines.append("")

    # Sleeve allocation
    lines.append("Sleeve allocation (active theses)")
    if summary.theses_by_sleeve:
        parts = [
            f"{k}={v}"
            for k, v in sorted(
                summary.theses_by_sleeve.items(),
                key=lambda kv: -kv[1],
            )
        ]
        lines.append(f"  {'  '.join(parts)}")
    else:
        lines.append("  (no active theses)")
    lines.append("")

    # Calibration + bias
    lines.append("Calibration + bias")
    if summary.calibration_error_in_window is not None:
        lines.append(
            f"  calibration error:   "
            f"{summary.calibration_error_in_window:.3f}"
        )
    else:
        lines.append("  calibration error:   (no records in window)")
    lines.append(f"  bias checks:         {summary.bias_checks_in_window}")
    lines.append("")

    lines.append("⚠️  advisory-only — no orders are routed.")
    return "\n".join(lines)


__all__ = [
    "InvestDashboardSummary",
    "build_invest_dashboard",
    "render_text",
]
