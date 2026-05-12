"""
Layer-2 synthesis for the research vertical — cluster MechanismCards by
*mechanism* (not by topic).

INTEGRATION NOTE — replace with graphify adapter when wired.
==========================================================
This module ships a heuristic Jaccard clusterer + an LLM clusterer as
the v0 implementation, mirroring the Plan A pattern in
``agent/research/ingest_router.py`` (heuristic / LLM-anthropic /
gbrain-mcp). The user has an external graphify project that does
graph-shaped entity clustering and is the right long-term backend for
Layer 2.

Follow-up PR scope: add a graphify path mirroring
``gbrain_adapter.fetch_from_export_file`` so ``run_synthesis`` can
delegate to graphify when available and fall back to the heuristic /
LLM paths otherwise. The MechanismCluster / SynthesisRun schemas are
the boundary contract; graphify's output just needs to validate
against them.

Until that adapter lands, the heuristic + LLM modes here are
intentionally simple — enough to surface obvious mechanism patterns
during the 40-day trial, not enough to be a permanent solution.
==========================================================

The Three-Layer Research OS asks two questions Layer 1 alone cannot
answer: (a) what mechanisms recur across the corpus? (b) what
first-principles + anti-patterns are shared? Clustering by topic gives
you what library catalogs already give you (same domain). Clustering by
*mechanism* surfaces transfer — papers in totally different topics that
exploit the same underlying causal structure.

Two modes:

* **LLM mode** (``llm_fn`` supplied): sends each card's
  (mechanism / first_principle / anti_pattern / transferability_test /
  one_sentence_compression / verdict) to a model and parses a structured
  clustering response. Quality depends on the LLM; the substrate just
  validates the JSON shape at the boundary.
* **Heuristic mode** (no ``llm_fn``): lexical Jaccard over the
  mechanism field. Won't surface deep transfer — but proves the pipeline
  works without an API key.

Storage: each run is one file at
``~/.neuro_os_research/synthesis/runs/<run_id>.json``. The dashboard reads
the most recent run within its window to surface cluster_count + briefs
status without re-clustering.

Read-only from the rest of the system; never mutates MechanismCards or
proposals (Law 7 — synthesis is interpretation, not data revision).
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from agent.research.framework import EMPTY_FRAMEWORK, Framework

logger = logging.getLogger(__name__)


# Heuristic-mode default similarity threshold for the lexical Jaccard.
DEFAULT_JACCARD_THRESHOLD = 0.25

# Heuristic-mode tokenization stopwords — kept tiny on purpose; we don't
# want to over-engineer a tiny path.
_HEURISTIC_STOPWORDS = frozenset({
    "the", "a", "an", "of", "to", "and", "or", "in", "on", "at", "is",
    "are", "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "by", "for", "with", "from", "as", "it", "its", "their",
    "we", "our", "they", "them", "which", "what", "when", "where",
    "how", "why", "than", "then", "so", "but", "if", "while",
    "via", "into", "onto", "out", "over", "under", "between",
    "through", "across", "about", "after", "before", "during",
})

_WORD_PATTERN = re.compile(r"\b[a-z][a-z\-]{2,}\b")


# Frontier-position taxonomy (per piece 1's Layer-2 spec). Optional on
# clusters — heuristic mode leaves it None; LLM mode may populate it.
FRONTIER_POSITION = Literal[
    "well_solved", "contested", "unsolved", "unsolved_neglected"
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MechanismCluster(BaseModel):
    """One cluster from a synthesis run. Frozen — clusters are
    interpretation snapshots, not mutable records."""

    model_config = ConfigDict(frozen=True)

    cluster_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    mechanism_summary: str = Field(min_length=1, max_length=1000)
    member_card_ids: Tuple[str, ...] = Field(min_length=1, max_length=50)
    shared_first_principle: Optional[str] = Field(default=None, max_length=400)
    recurring_anti_pattern: Optional[str] = Field(default=None, max_length=400)
    frontier_position: Optional[FRONTIER_POSITION] = None
    false_consensus_flag: Optional[str] = Field(default=None, max_length=400)
    framework_axes_touched: Tuple[str, ...] = Field(default_factory=tuple, max_length=12)


class SynthesisRun(BaseModel):
    """One ``research synthesize`` invocation. Stored at
    ``~/.neuro_os_research/synthesis/runs/<run_id>.json``."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    window_days: int = Field(ge=1, le=365)
    min_cluster_size: int = Field(ge=1, le=20)
    method: Literal["llm-anthropic", "fallback-heuristic"]
    framework_name: str = "(none)"
    input_card_count: int = Field(ge=0)
    clusters: Tuple[MechanismCluster, ...] = Field(default_factory=tuple)
    unclustered_card_ids: Tuple[str, ...] = Field(default_factory=tuple)
    note: Optional[str] = Field(default=None, max_length=1000)


# Callable shape mirroring the ingest one — (system_prompt, user_text) → list of dicts.
LLMClusterCallable = Callable[[str, str], List[dict]]


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------


def _research_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_research")


def synthesis_dir(home: Optional[Path] = None) -> Path:
    return _research_home(home) / "synthesis" / "runs"


def _atomic_write_json(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=".json.tmp", dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def write_synthesis_run(run: SynthesisRun, *, home: Optional[Path] = None) -> Path:
    target = synthesis_dir(home) / f"{run.run_id}.json"
    _atomic_write_json(target, run.model_dump_json(indent=2))
    return target


def list_synthesis_runs(
    *,
    home: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[SynthesisRun]:
    """Most-recent first (by generated_at)."""
    d = synthesis_dir(home)
    if not d.exists():
        return []
    runs: List[SynthesisRun] = []
    for p in d.glob("*.json"):
        try:
            runs.append(SynthesisRun.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    runs.sort(key=lambda r: r.generated_at, reverse=True)
    return runs[:limit] if limit else runs


def read_synthesis_run(
    run_id: str, *, home: Optional[Path] = None,
) -> Optional[SynthesisRun]:
    path = synthesis_dir(home) / f"{run_id}.json"
    if not path.exists():
        return None
    return SynthesisRun.model_validate_json(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Card loading (within window)
# ---------------------------------------------------------------------------


def _parse_ts(raw: Optional[str]) -> Optional[datetime]:
    if not isinstance(raw, str):
        return None
    try:
        ts = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def load_accepted_cards_in_window(
    *,
    home: Optional[Path] = None,
    window_days: int = 30,
    now: Optional[datetime] = None,
) -> List[dict]:
    """Load accepted MechanismCards within the window as plain dicts.

    Returns plain dicts (not Pydantic models) because the synthesis layer
    is one-way (read-only consumer); we don't want to recursively import
    MechanismCard's domain config and pull in the substrate. The dicts
    are validated only for the fields synthesis actually reads.
    """
    when = now or datetime.now(timezone.utc)
    cutoff = when - timedelta(days=window_days)
    cards_dir = _research_home(home) / "mechanism_cards"
    if not cards_dir.exists():
        return []
    out: List[dict] = []
    for p in cards_dir.glob("*.json"):
        try:
            body = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = _parse_ts(body.get("ts"))
        if ts is None or ts < cutoff:
            continue
        if not isinstance(body.get("id"), str):
            continue
        if not isinstance(body.get("mechanism"), str):
            continue
        out.append(body)
    out.sort(key=lambda c: _parse_ts(c.get("ts")) or when)
    return out


# ---------------------------------------------------------------------------
# Heuristic clustering (lexical Jaccard on `mechanism` field)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    tokens = _WORD_PATTERN.findall(text.lower())
    return {t for t in tokens if t not in _HEURISTIC_STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _heuristic_cluster(
    cards: List[dict],
    *,
    threshold: float = DEFAULT_JACCARD_THRESHOLD,
    min_cluster_size: int = 2,
) -> Tuple[List[MechanismCluster], List[str]]:
    """Greedy clustering — for each unassigned card, find all others with
    Jaccard ≥ threshold on the mechanism token set; if the resulting
    group has ≥ min_cluster_size cards, emit it as a cluster.

    Deterministic: card ordering is preserved from input."""
    tokens = [_tokenize(c.get("mechanism", "")) for c in cards]
    assigned = [False] * len(cards)
    clusters: List[MechanismCluster] = []
    unclustered: List[str] = []
    for i, card_i in enumerate(cards):
        if assigned[i]:
            continue
        group_idx = [i]
        for j in range(i + 1, len(cards)):
            if assigned[j]:
                continue
            if _jaccard(tokens[i], tokens[j]) >= threshold:
                group_idx.append(j)
        if len(group_idx) >= min_cluster_size:
            for k in group_idx:
                assigned[k] = True
            shared_tokens = tokens[group_idx[0]].copy()
            for k in group_idx[1:]:
                shared_tokens &= tokens[k]
            label = ", ".join(sorted(shared_tokens)[:5]) or "mechanism cluster"
            members = tuple(cards[k].get("id", "?") for k in group_idx)
            mechanism_summary = " | ".join(
                str(cards[k].get("mechanism", ""))[:140] for k in group_idx[:5]
            )[:1000]
            # Union of framework_alignment axes across members (heuristic
            # has no LLM to interpret transfers, but propagates whatever
            # axes the members already carry).
            axes: set[str] = set()
            for k in group_idx:
                for a in (cards[k].get("framework_alignment") or []):
                    if isinstance(a, dict):
                        name = a.get("axis_name") or a.get("axis")
                        if isinstance(name, str):
                            axes.add(name)
            clusters.append(MechanismCluster(
                cluster_id=f"hcluster-{uuid.uuid4().hex[:10]}",
                label=label[:120],
                mechanism_summary=mechanism_summary or "(no shared mechanism text)",
                member_card_ids=members,
                framework_axes_touched=tuple(sorted(axes))[:12],
            ))
    for i, card in enumerate(cards):
        if not assigned[i]:
            unclustered.append(str(card.get("id", "?")))
    return clusters, unclustered


# ---------------------------------------------------------------------------
# LLM clustering
# ---------------------------------------------------------------------------


_LLM_SYSTEM_PROMPT = (
    "You cluster MechanismCards by their underlying causal mechanism — "
    "NOT by topic or paper field. Two cards belong in the same cluster "
    "when they exploit the same causal structure, even if their domains "
    "are different. Two cards in the same topic with different causal "
    "stories belong in DIFFERENT clusters.\n\n"
    "Input: a JSON array of cards, each with id / mechanism / "
    "first_principle / anti_pattern / transferability_test / "
    "one_sentence_compression / verdict (some fields may be null).\n\n"
    "Output: a JSON array of cluster objects. Each cluster has: "
    "label (≤ 120 chars, the cluster's short name), "
    "mechanism_summary (≤ 1000 chars, what's shared across members), "
    "member_card_ids (list of card ids in the cluster — every id MUST "
    "appear in the input array), "
    "shared_first_principle (≤ 400 chars, optional — the deepest truth "
    "all members rest on), "
    "recurring_anti_pattern (≤ 400 chars, optional — the way this "
    "mechanism is commonly misapplied), "
    "frontier_position (optional, one of 'well_solved' | 'contested' | "
    "'unsolved' | 'unsolved_neglected'), "
    "false_consensus_flag (≤ 400 chars, optional — name a place the "
    "field appears to agree but the evidence is thin), "
    "framework_axes_touched (optional list of axis names from the user "
    "framework, if supplied).\n\n"
    "RULES: every cluster MUST have at least the min_cluster_size members "
    "supplied in the user message; cards that don't fit any mechanism "
    "should be LEFT OUT of all clusters (do not invent singleton clusters); "
    "prefer FEWER, sharper clusters over many shallow ones."
)


def _build_llm_user_message(
    cards: List[dict],
    *,
    min_cluster_size: int,
    framework: Framework,
) -> str:
    """Build the user message: framework directive + min_cluster_size +
    a JSON-ish view of the cards with the deepened fields."""
    parts: List[str] = []
    if framework.axes:
        parts.append("USER FRAMEWORK — populate framework_axes_touched ONLY from these:")
        for axis in framework.axes:
            desc = f" — {axis.description}" if axis.description else ""
            parts.append(f"  - {axis.name}{desc}")
        parts.append("")
    parts.append(f"min_cluster_size: {min_cluster_size}")
    parts.append("")
    # Lightweight card serialization — only the fields synthesis cares about.
    payload = [
        {
            "id": c.get("id"),
            "mechanism": c.get("mechanism"),
            "first_principle": c.get("first_principle"),
            "anti_pattern": c.get("anti_pattern"),
            "transferability_test": c.get("transferability_test"),
            "one_sentence_compression": c.get("one_sentence_compression"),
            "verdict": c.get("verdict"),
        }
        for c in cards
    ]
    parts.append("CARDS:")
    parts.append(json.dumps(payload, indent=2, default=str))
    return "\n".join(parts)


def _llm_cluster(
    cards: List[dict],
    *,
    llm_fn: LLMClusterCallable,
    min_cluster_size: int,
    framework: Framework,
) -> Tuple[List[MechanismCluster], List[str]]:
    """Call the LLM, parse the cluster array. Malformed responses → empty
    clusters (caller falls back to heuristic)."""
    user_msg = _build_llm_user_message(
        cards, min_cluster_size=min_cluster_size, framework=framework,
    )
    try:
        raw_rows = llm_fn(_LLM_SYSTEM_PROMPT, user_msg)
    except Exception as e:
        logger.warning("synthesis._llm_cluster: llm_fn failed (%s)", e)
        return [], [str(c.get("id", "?")) for c in cards]

    valid_ids = {str(c.get("id")) for c in cards}
    clusters: List[MechanismCluster] = []
    seen_member_ids: set[str] = set()
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        member_ids_raw = row.get("member_card_ids") or row.get("members") or []
        members = [str(m) for m in member_ids_raw if str(m) in valid_ids]
        if len(members) < min_cluster_size:
            continue
        members = tuple(dict.fromkeys(members))  # dedup preserving order
        seen_member_ids.update(members)
        axes_raw = row.get("framework_axes_touched") or []
        axes = tuple(
            str(a) for a in axes_raw if isinstance(a, str)
        )[:12]
        frontier = row.get("frontier_position")
        if frontier not in ("well_solved", "contested", "unsolved", "unsolved_neglected"):
            frontier = None
        try:
            clusters.append(MechanismCluster(
                cluster_id=f"lcluster-{uuid.uuid4().hex[:10]}",
                label=str(row.get("label", "cluster"))[:120] or "cluster",
                mechanism_summary=str(row.get("mechanism_summary", ""))[:1000]
                                  or "(no summary supplied)",
                member_card_ids=members,
                shared_first_principle=_opt_str(row.get("shared_first_principle"), 400),
                recurring_anti_pattern=_opt_str(row.get("recurring_anti_pattern"), 400),
                frontier_position=frontier,
                false_consensus_flag=_opt_str(row.get("false_consensus_flag"), 400),
                framework_axes_touched=axes,
            ))
        except Exception as e:
            logger.warning(
                "synthesis._llm_cluster: dropped row (validation: %s)", e,
            )
    unclustered = sorted(valid_ids - seen_member_ids)
    return clusters, unclustered


def _opt_str(raw: object, max_len: int) -> Optional[str]:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    return s[:max_len] if s else None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def cluster_proposals(
    cards: List[dict],
    *,
    llm_fn: Optional[LLMClusterCallable] = None,
    min_cluster_size: int = 2,
    framework: Optional[Framework] = None,
    threshold: float = DEFAULT_JACCARD_THRESHOLD,
) -> Tuple[List[MechanismCluster], List[str]]:
    """Cluster a list of card dicts. Public for tests + reuse.

    Returns (clusters, unclustered_card_ids).
    """
    fw = framework or EMPTY_FRAMEWORK
    if llm_fn is None:
        return _heuristic_cluster(
            cards, threshold=threshold, min_cluster_size=min_cluster_size,
        )
    return _llm_cluster(
        cards, llm_fn=llm_fn, min_cluster_size=min_cluster_size, framework=fw,
    )


def run_synthesis(
    *,
    home: Optional[Path] = None,
    window_days: int = 30,
    min_cluster_size: int = 2,
    llm_fn: Optional[LLMClusterCallable] = None,
    framework: Optional[Framework] = None,
    now: Optional[datetime] = None,
    threshold: float = DEFAULT_JACCARD_THRESHOLD,
) -> SynthesisRun:
    """End-to-end synthesis: load → cluster → write SynthesisRun.

    If ``framework`` is None, the user framework is auto-loaded from
    ``framework.json`` (or returns EMPTY_FRAMEWORK if missing).
    """
    when = now or datetime.now(timezone.utc)
    if framework is None:
        from agent.research.framework import load_framework
        framework = load_framework(home=home)

    cards = load_accepted_cards_in_window(
        home=home, window_days=window_days, now=when,
    )
    method: Literal["llm-anthropic", "fallback-heuristic"] = (
        "llm-anthropic" if llm_fn is not None else "fallback-heuristic"
    )
    clusters, unclustered = cluster_proposals(
        cards,
        llm_fn=llm_fn,
        min_cluster_size=min_cluster_size,
        framework=framework,
        threshold=threshold,
    )

    note: Optional[str] = None
    if not cards:
        note = "no accepted mechanism cards in window"
    elif not clusters:
        note = (
            f"{len(cards)} cards but no clusters at "
            f"min_cluster_size={min_cluster_size}"
        )

    run = SynthesisRun(
        run_id=f"synth-{uuid.uuid4().hex[:10]}",
        generated_at=when,
        window_days=window_days,
        min_cluster_size=min_cluster_size,
        method=method,
        framework_name=framework.name,
        input_card_count=len(cards),
        clusters=tuple(clusters),
        unclustered_card_ids=tuple(unclustered),
        note=note,
    )
    write_synthesis_run(run, home=home)
    return run


__all__ = [
    "DEFAULT_JACCARD_THRESHOLD",
    "FRONTIER_POSITION",
    "MechanismCluster",
    "SynthesisRun",
    "LLMClusterCallable",
    "synthesis_dir",
    "write_synthesis_run",
    "list_synthesis_runs",
    "read_synthesis_run",
    "load_accepted_cards_in_window",
    "cluster_proposals",
    "run_synthesis",
]
