"""
Daily anchors — typed log for faith / relational pillars.

Paul's week plan has three anchors: (1) daily walk with God, (2)
restoration with Taylor, (3) AI-businesses-from-neuro-OS. The third
is what the existing 4 verticals already track. The first two need
a tiny typed log so the dashboard can answer "did I hit my faith
anchor 7/7 days this week? Relational anchor 5/7?".

Intentionally NOT a new vertical: anchors don't have drift modes,
constructive expressions, or a contract. They are append-only daily
markers — "I prayed/walked/talked-to-Taylor today." The nightly
summary counts them per kind so the dashboard surfaces the streak.

Storage: ``~/.founder_loop/anchors.jsonl`` (append-only).
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


AnchorKind = Literal["faith", "relational"]


class Anchor(BaseModel):
    """One daily anchor entry. Frozen — once written, immutable."""

    model_config = ConfigDict(frozen=True)

    anchor_id: str = Field(min_length=1, max_length=64)
    ts: datetime
    kind: AnchorKind
    context: str = Field(
        min_length=1,
        max_length=400,
        description=(
            "Short free-text marker for what happened. e.g. "
            "'5:50am prayer + walk + plan done'; "
            "'Taylor: cooked dinner together, talked about week'."
        ),
    )


def _anchors_path(home: Optional[Path] = None) -> Path:
    base = home or (Path.home() / ".founder_loop")
    return base / "anchors.jsonl"


def write_anchor(
    *,
    kind: AnchorKind,
    context: str,
    home: Optional[Path] = None,
    ts: Optional[datetime] = None,
) -> Anchor:
    """Append one Anchor. Atomic line-write via os.write+fsync."""
    when = ts or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    anchor = Anchor(
        anchor_id=uuid.uuid4().hex[:16],
        ts=when,
        kind=kind,
        context=context,
    )
    path = _anchors_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (anchor.model_dump_json() + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        written = 0
        while written < len(line):
            n = os.write(fd, line[written:])
            if n <= 0:
                raise OSError("os.write returned 0 — disk full?")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)
    return anchor


def read_anchors(
    *,
    home: Optional[Path] = None,
    kind: Optional[AnchorKind] = None,
    since: Optional[datetime] = None,
) -> List[Anchor]:
    """Return all anchors, optionally filtered. Skips malformed lines."""
    path = _anchors_path(home)
    if not path.exists():
        return []
    out: List[Anchor] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                a = Anchor.model_validate_json(line)
            except Exception:
                continue
            if kind is not None and a.kind != kind:
                continue
            if since is not None:
                ts = a.ts if a.ts.tzinfo else a.ts.replace(tzinfo=timezone.utc)
                cutoff = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
            out.append(a)
    return out


def count_anchors_per_day(
    *,
    home: Optional[Path] = None,
    kind: AnchorKind,
    days: int,
    now: Optional[datetime] = None,
) -> tuple[int, int]:
    """Returns (days_hit, days_window).

    ``days_hit`` = distinct calendar days within the last ``days``
    (inclusive of ``now``'s calendar date) that had at least one anchor
    of the given ``kind``. ``days_window`` equals ``days``. So a value
    like ``(5, 7)`` reads as "anchors hit on 5 of the last 7 days,
    including today."

    The "anchor lit" semantic is per-day, not per-event: 3 prayer
    entries on the same day count as ONE day-hit.

    Calendar-day boundaries are evaluated in the timezone of each
    anchor's ``ts``; we don't try to reconcile across timezones, which
    is the right move for a single-user local tool.
    """
    when = now or datetime.now(timezone.utc)
    today = when.date()
    earliest = today - timedelta(days=days - 1)  # inclusive
    hits: set[date] = set()
    for a in read_anchors(home=home, kind=kind):
        d = a.ts.date()
        if earliest <= d <= today:
            hits.add(d)
    return (len(hits), days)


__all__ = [
    "AnchorKind",
    "Anchor",
    "write_anchor",
    "read_anchors",
    "count_anchors_per_day",
]
