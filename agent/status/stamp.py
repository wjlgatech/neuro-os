"""
PlanStamp — the YAML frontmatter schema every stamped doc carries.

Stamp shape (top of a plan file):

    ---
    status: active        # active | parked | done | abandoned
    parent: phase-1-paper # parent goal — one of the 5 enum values
    acceptance: "..."     # optional; concrete artifact for status=active
    reason: "..."         # optional; why parked, for status=parked
    ---

    # Real title of the plan
    ...

Last-touched is NOT in the stamp. It is derived from `git log -1 --format=%ai`
on each file by the walker, so a stale author claim cannot lie about freshness.

Per Law 1 (no raw inputs into the substrate): YAML → PlanStamp goes through
Pydantic validation. A typo in `status:` or `parent:` raises ValidationError
and the walker surfaces the file path so the user can fix it.

Frozen: stamps are read-only at runtime. Editing a stamp means editing the
file, not mutating the model.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# Status taxonomy. Kept small on purpose; if you need a 5th value, name
# the failure mode it covers and add it via a tested PR.
StampStatus = Literal["active", "parked", "done", "abandoned"]


# Parent-goal taxonomy. Maps every plan to the *one* north-star bucket it
# feeds. "other" is the escape hatch for genuinely cross-cutting work; if
# more than ~20% of plans land in "other", split the taxonomy.
ParentGoal = Literal[
    "phase-1-paper",     # mechanism-survival paper (arXiv July 2026, ICLR 2027)
    "phase-3-moonshot",  # NeurIPS 2027 continual world models for Physical AI
    "invest",            # invest vertical features + dogfooding
    "infra",             # substrate / framework / engineering principles
    "other",             # escape hatch — name the gap when you use it
]


class PlanStamp(BaseModel):
    """The frontmatter stamp itself. One per docs/**/*.md plan/PRD/roadmap file.

    Frozen — if you need to revise the stamp, edit the file's frontmatter,
    don't mutate the model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: StampStatus
    parent: ParentGoal
    acceptance: Optional[str] = Field(
        default=None,
        max_length=400,
        description="Concrete artifact / observable that lets you mark "
                    "this 'done'. Required-in-spirit when status=active; "
                    "ignored otherwise.",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=400,
        description="Why this is parked + what would un-park it. "
                    "Required-in-spirit when status=parked; ignored otherwise.",
    )


class StampedPlan(BaseModel):
    """A PlanStamp paired with the file metadata derived from disk + git.

    The walker emits these; render.py groups by parent + status and writes
    them to STATUS.md. Frozen so the render path is a pure function.
    """

    model_config = ConfigDict(frozen=True)

    path: Path
    title: str = Field(
        min_length=1,
        max_length=200,
        description="First `# ` heading in the file. Used as the link label.",
    )
    stamp: PlanStamp
    last_touched: Optional[date] = Field(
        default=None,
        description="Most recent commit date for this file (from `git log "
                    "-1 --format=%ai`). None if the file is untracked.",
    )


__all__ = [
    "StampStatus",
    "ParentGoal",
    "PlanStamp",
    "StampedPlan",
]
