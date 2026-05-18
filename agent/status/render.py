"""
Render STATUS.md from stamped plans + recent ships + a north-star config.

Pure function: same inputs → same output. Idempotent — running the
sync pipeline twice produces a byte-identical file (only ``generated_at``
embedded in the body is allowed to change, and we make that opt-in).

Output regions:
  1. Header (title + Last updated + Last commit at update + the
     freshness-warning blockquote).
  2. One sentence (north-star, from config).
  3. Where we are (3 most recent ships).
  4. Active this week (status=active rows, sorted by parent then path).
  5. Parked but real (status=parked rows).
  6. Done this cycle (status=done rows, since the last shipped row).
  7. Where to look for detail (link table — everything, grouped by parent).
  8. Weekly ritual (boilerplate, from config).
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from agent.status.git_recent import RecentShip
from agent.status.stamp import ParentGoal, StampedPlan


class NorthStarConfig(BaseModel):
    """Static configuration the renderer needs but the walker can't supply.

    Frozen. v0 lives in code; v1 could move to docs/status_config.yaml.
    """

    model_config = ConfigDict(frozen=True)

    one_sentence: str = Field(min_length=1, max_length=2000)
    weekly_ritual_lines: List[str] = Field(default_factory=list)
    not_happening_lines: List[str] = Field(
        default_factory=list,
        description="Things explicitly NOT happening this month — keeps "
                    "old loops closed.",
    )


# Display order of parent goals in the link table + active table.
_PARENT_ORDER: List[ParentGoal] = [
    "phase-1-paper",
    "phase-3-moonshot",
    "invest",
    "infra",
    "other",
]

_PARENT_LABEL: Dict[ParentGoal, str] = {
    "phase-1-paper": "Phase 1 — mechanism-survival paper",
    "phase-3-moonshot": "Phase 3 — NeurIPS 2027 moonshot",
    "invest": "Investment vertical",
    "infra": "Substrate / infra",
    "other": "Other",
}


def _format_path(path, docs_root):
    """Render a path as a markdown link relative to the STATUS.md location.

    STATUS.md lives at docs/STATUS.md; paths are relative to docs/.
    """
    try:
        rel = path.relative_to(docs_root)
    except ValueError:
        rel = path
    return str(rel)


def _by_parent(
    plans: List[StampedPlan],
    *,
    status: Optional[str] = None,
) -> Dict[ParentGoal, List[StampedPlan]]:
    """Group ``plans`` by parent goal, optionally filtered by status."""
    buckets: Dict[ParentGoal, List[StampedPlan]] = {p: [] for p in _PARENT_ORDER}
    for p in plans:
        if status is not None and p.stamp.status != status:
            continue
        buckets[p.stamp.parent].append(p)
    # Sort each bucket by path for stable output.
    for k in buckets:
        buckets[k].sort(key=lambda x: str(x.path))
    return buckets


def _section_header(text: str) -> str:
    return f"\n## {text}\n"


def build_status_markdown(
    *,
    plans: List[StampedPlan],
    recent: List[RecentShip],
    config: NorthStarConfig,
    docs_root,
    today: Optional[date] = None,
) -> str:
    """Build the full STATUS.md text. Pure function."""
    today = today or date.today()

    parts: List[str] = []

    # 1. Header
    parts.append("# STATUS — neuro-os\n")
    parts.append(f"**Last updated:** {today.isoformat()} (auto-generated)\n")
    if recent:
        head = recent[0]
        parts.append(
            f"**Last commit at update:** `{head.sha}` "
            f"({head.date.isoformat()} — {head.subject})\n"
        )
    parts.append("")
    parts.append(
        "> Single-page \"where am I\" snapshot. **Auto-generated** by "
        "`scripts/sync_status.py` from frontmatter stamps on each plan "
        "file + recent git log + a small north-star config. "
        "Do NOT hand-edit this file — edit the stamps on individual plan "
        "files; the pre-commit hook re-renders this on every commit."
    )
    parts.append("")
    parts.append(
        "> If `Last updated` above is more than 14 days ago, **stop "
        "and fix the staleness before touching code**. The pre-commit "
        "hook ensures this can only happen if no commits have landed "
        "in 14+ days, which itself is the bug."
    )
    parts.append("")

    # 2. One sentence
    parts.append(_section_header("One sentence (north-star)"))
    parts.append(config.one_sentence)
    parts.append("")

    # 3. Where we are
    parts.append(_section_header("Where we are"))
    parts.append("**3 most recent ships** (from `git log -3`):")
    parts.append("")
    if recent:
        parts.append("| Date | SHA | Subject |")
        parts.append("|---|---|---|")
        for r in recent:
            subj = r.subject.replace("|", "\\|")
            parts.append(f"| {r.date.isoformat()} | `{r.sha}` | {subj} |")
    else:
        parts.append("_(no commits yet)_")
    parts.append("")

    # 4. Active this week
    parts.append(_section_header("Active this week"))
    active_buckets = _by_parent(plans, status="active")
    any_active = any(active_buckets[p] for p in _PARENT_ORDER)
    if not any_active:
        parts.append("_(nothing marked status=active — set status: active on "
                     "the plan you're working on today)_")
    else:
        parts.append("| Parent | Plan | Acceptance | Last touched |")
        parts.append("|---|---|---|---|")
        for parent in _PARENT_ORDER:
            for p in active_buckets[parent]:
                rel = _format_path(p.path, docs_root)
                title = p.title.replace("|", "\\|")
                acc = (p.stamp.acceptance or "_(no acceptance set)_").replace("|", "\\|")
                lt = p.last_touched.isoformat() if p.last_touched else "—"
                parts.append(
                    f"| {_PARENT_LABEL[parent]} | [{title}]({rel}) | {acc} | {lt} |"
                )
    parts.append("")

    # 5. Parked but real
    parts.append(_section_header("Parked but real (not abandoned)"))
    parked_buckets = _by_parent(plans, status="parked")
    any_parked = any(parked_buckets[p] for p in _PARENT_ORDER)
    if not any_parked:
        parts.append("_(nothing parked)_")
    else:
        for parent in _PARENT_ORDER:
            rows = parked_buckets[parent]
            if not rows:
                continue
            parts.append(f"**{_PARENT_LABEL[parent]}**")
            for p in rows:
                rel = _format_path(p.path, docs_root)
                title = p.title
                reason = p.stamp.reason or "_(no reason given)_"
                parts.append(f"- [{title}]({rel}) — {reason}")
            parts.append("")

    # 6. Done this cycle
    done_buckets = _by_parent(plans, status="done")
    any_done = any(done_buckets[p] for p in _PARENT_ORDER)
    if any_done:
        parts.append(_section_header("Done this cycle"))
        for parent in _PARENT_ORDER:
            rows = done_buckets[parent]
            if not rows:
                continue
            parts.append(f"**{_PARENT_LABEL[parent]}**")
            for p in rows:
                rel = _format_path(p.path, docs_root)
                lt = p.last_touched.isoformat() if p.last_touched else "—"
                parts.append(f"- [{p.title}]({rel}) — last touched {lt}")
            parts.append("")

    # 7. What's NOT happening
    if config.not_happening_lines:
        parts.append(_section_header(
            "What's actively NOT happening (don't reopen by accident)"
        ))
        for line in config.not_happening_lines:
            parts.append(f"- {line}")
        parts.append("")

    # 8. Where to look for detail
    parts.append(_section_header("Where to look for detail (the spine)"))
    parts.append(
        "Every stamped plan, grouped by parent. `status` tells you what's "
        "active/parked/done/abandoned at a glance."
    )
    parts.append("")
    parts.append("| Parent | Plan | Status | Last touched |")
    parts.append("|---|---|---|---|")
    by_parent_all = _by_parent(plans)
    for parent in _PARENT_ORDER:
        for p in by_parent_all[parent]:
            rel = _format_path(p.path, docs_root)
            lt = p.last_touched.isoformat() if p.last_touched else "—"
            parts.append(
                f"| {_PARENT_LABEL[parent]} | [{p.title}]({rel}) | "
                f"`{p.stamp.status}` | {lt} |"
            )
    parts.append("")
    parts.append("**Reference docs** (not stamped — load-bearing background):")
    parts.append("")
    parts.append("- [AI_NATIVE_ENGINEERING_PRINCIPLES.md](AI_NATIVE_ENGINEERING_PRINCIPLES.md) — 10 laws + enforcement tags")
    parts.append("- [how-it-works.md](how-it-works.md), [how-to-use-it.md](how-to-use-it.md), [what-is-this.md](what-is-this.md) — user-facing intros")
    parts.append("- [prd/](prd/) — product requirement drafts")
    parts.append("")

    # 9. Weekly ritual
    if config.weekly_ritual_lines:
        parts.append(_section_header("Weekly ritual (5 min, Sundays)"))
        for i, line in enumerate(config.weekly_ritual_lines, start=1):
            parts.append(f"{i}. {line}")
        parts.append("")

    # Footer pin
    parts.append("---")
    parts.append(
        "_This file is generated by `scripts/sync_status.py`. Edit the "
        "frontmatter stamps on individual plan files (or the north-star "
        "config in `agent/status/render.py`) — never STATUS.md directly._"
    )
    parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Default north-star config for this repo. Tweak the one_sentence /
# weekly_ritual_lines / not_happening_lines here when those change.
# v1 idea: move to docs/status_config.yaml so editing it doesn't require
# a code commit. v0 = ship it in code.
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = NorthStarConfig(
    one_sentence=(
        "Neuro-os is a four-vertical AI substrate "
        "(`founder_loop` / `research` / `investment` / `startup`) "
        "Paul uses to compound personal practice into research output. "
        "Two-phase arc: **Phase 1** = mechanism-survival paper "
        "(arXiv-first July 2026, ICLR 2027 primary) — the wedge that "
        "earns trust + schema + co-authors. **Phase 3** = continual "
        "world models for Physical AI on construction sites "
        "(NeurIPS 2027 moonshot, ProCore application). Phase 1 unlocks "
        "Phase 3."
    ),
    weekly_ritual_lines=[
        "Skim **Active this week** — does it match what you actually want to be doing? If not, move stamps.",
        "Look at **Last touched** dates — any active row >7 days cold? Either revive or mark parked.",
        "Re-read **Parked but real** — any row parked >30 days? Decide: revive or abandon (delete the file).",
        "If you skipped a week, add a one-line note in the parent plan you most recently touched. Don't lie.",
        "Confirm at least one active row's `Last touched` is <7 days. If not, the project is sleeping — that's data.",
    ],
    not_happening_lines=[
        "No Phase 3 (NeurIPS 2027) code yet — depends on Phase 1 paper signal.",
        "No broker integration in invest vertical — advisory-only is a hard invariant.",
        "No catalog mutation across the 4 verticals — `mutable_paths=[]` locked per Law 7.",
        "No multi-currency support for invest workflow — USD only, v0 scope.",
    ],
)


__all__ = [
    "NorthStarConfig",
    "build_status_markdown",
    "DEFAULT_CONFIG",
]
