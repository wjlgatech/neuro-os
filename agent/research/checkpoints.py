"""
Stop-condition checkpoints for the research vertical.

The Three-Layer Research OS is a beautiful trap if it's not honest about
whether it's working. The checkpoint is the simplest gate that catches
the trap: after each synthesis cycle, the user logs two binary signals:

  1. brief_produced       — did the cycle actually produce a usable brief?
  2. mental_model_clearer — did your understanding of the active thesis
                            get clearer because of it?

Both YES → the system is working; keep adding inputs.
Either NO twice in a row → the system is broken; redesign before adding
                           more inputs.

The dashboard surfaces a system_not_converging flag when ≥ 2 consecutive
checkpoints are non-converging (either field False). This module just
stores the events and computes the streak; the dashboard reads it.

Storage: JSONL at ``~/.neuro_os_research/checkpoints.jsonl`` (append-only,
one event per line). Append is atomic (single open() with "a" mode under
contention from one user is safe on POSIX; the substrate doesn't promise
multi-process correctness because the design audience is one user).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ResearchCheckpoint(BaseModel):
    """One stop-condition observation. Frozen — checkpoints are events,
    not editable records."""

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str = Field(min_length=1, max_length=64)
    ts: datetime
    brief_produced: bool
    mental_model_clearer: bool
    note: Optional[str] = Field(default=None, max_length=600)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _research_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_research")


def checkpoints_path(home: Optional[Path] = None) -> Path:
    return _research_home(home) / "checkpoints.jsonl"


def write_checkpoint(
    checkpoint: ResearchCheckpoint, *, home: Optional[Path] = None,
) -> Path:
    """Append one checkpoint to ``checkpoints.jsonl``. Creates the
    parent directory if missing."""
    target = checkpoints_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = checkpoint.model_dump_json() + "\n"
    # Append-and-fsync — atomic enough for single-user JSONL.
    with open(target, "a", encoding="utf-8") as f:
        f.write(body)
        f.flush()
        try:
            os.fsync(f.fileno())
        except (OSError, AttributeError):
            pass
    return target


def read_checkpoints(
    *,
    home: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[ResearchCheckpoint]:
    """Read all checkpoints, oldest first. ``limit`` returns the
    LATEST N (after sorting)."""
    target = checkpoints_path(home)
    if not target.exists():
        return []
    out: List[ResearchCheckpoint] = []
    with target.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(ResearchCheckpoint.model_validate_json(line))
            except Exception:
                continue
    out.sort(key=lambda c: c.ts)
    if limit:
        return out[-limit:]
    return out


# ---------------------------------------------------------------------------
# Derived signals
# ---------------------------------------------------------------------------


def is_converging(checkpoint: ResearchCheckpoint) -> bool:
    """A checkpoint is 'converging' iff BOTH binary signals are true.
    Either-False is treated as non-converging by design — the system
    has to produce a brief AND clarify your mental model for the cycle
    to count as working."""
    return bool(checkpoint.brief_produced and checkpoint.mental_model_clearer)


def recent_no_streak(
    *,
    home: Optional[Path] = None,
    k: int = 5,
) -> int:
    """Return the length of the trailing run of non-converging
    checkpoints in the last ``k`` events (most recent first).

    Examples:
      checkpoints (oldest→newest): [Y, Y, N]      → returns 1
      checkpoints:                 [Y, N, N]      → returns 2 (warning fires)
      checkpoints:                 [N, Y, Y]      → returns 0
      empty:                                       → returns 0
    """
    events = read_checkpoints(home=home, limit=k)
    streak = 0
    for ckpt in reversed(events):  # newest first
        if is_converging(ckpt):
            break
        streak += 1
    return streak


def latest_checkpoint(
    *, home: Optional[Path] = None,
) -> Optional[ResearchCheckpoint]:
    """Return the most recent checkpoint, or None if file is empty."""
    events = read_checkpoints(home=home, limit=1)
    return events[-1] if events else None


# Convergence warning threshold: when ≥ THIS_MANY consecutive
# non-converging checkpoints appear, the dashboard surfaces
# `system_not_converging`. 2 is intentional — one bad cycle is noise;
# two in a row is a pattern.
CONVERGENCE_WARNING_THRESHOLD = 2


def now_utc() -> datetime:
    """Helper kept here so tests can monkeypatch."""
    return datetime.now(timezone.utc)


__all__ = [
    "ResearchCheckpoint",
    "CONVERGENCE_WARNING_THRESHOLD",
    "checkpoints_path",
    "write_checkpoint",
    "read_checkpoints",
    "is_converging",
    "recent_no_streak",
    "latest_checkpoint",
    "now_utc",
]
