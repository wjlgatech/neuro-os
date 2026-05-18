"""
agent.status — auto-sync pipeline for docs/STATUS.md.

The kitchen-whiteboard for a returning developer / Claude instance.
STATUS.md is the single page that answers what/why/where/next. It is
**generated**, not hand-edited, from:

  1. YAML frontmatter "stamps" on each docs/plans/*.md and docs/prd/*.md
     and docs/roadmap.md (status, parent goal, acceptance/reason).
  2. Recent git log (the 3 most recent commits → recent ships).
  3. A small NorthStarConfig (one sentence + weekly ritual text).

Pipeline:
  StampedPlan[] + RecentShip[] + NorthStarConfig
    → render.build_status_markdown()
    → docs/STATUS.md

Run via:
  python scripts/sync_status.py --write
  neuro-os status [--sync]

Pre-commit hook runs `sync_status.py --write` and re-stages STATUS.md
before every commit, so staleness is structurally impossible.
"""
from __future__ import annotations

from agent.status.git_recent import RecentShip, get_recent_ships
from agent.status.render import (
    NorthStarConfig,
    build_status_markdown,
)
from agent.status.stamp import PlanStamp, ParentGoal, StampStatus, StampedPlan
from agent.status.walker import walk_stamped_plans


__all__ = [
    "PlanStamp",
    "ParentGoal",
    "StampStatus",
    "StampedPlan",
    "RecentShip",
    "get_recent_ships",
    "NorthStarConfig",
    "build_status_markdown",
    "walk_stamped_plans",
]
