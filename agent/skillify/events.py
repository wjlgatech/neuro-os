"""
Override events — the input data for skillify pattern extraction.

When the user picks something OTHER than the constructive expression
the substrate proposed, that's evidence that the catalog's default
isn't matching reality. After N such overrides on the same drift
mode, we propose a new ConstructiveExpression to /catalog-review (the
human gate Law 7 enforces).

v0 ships manual logging via CLI: the user types
``neuro-os skillify log-override --vertical research --drift
paper_collector --user-action "I extracted into a Markdown brief
instead"``. v1 will auto-emit OverrideEvents from the chat surfaces
(founder_loop conversation manager, /research-review, etc.) when the
user accepts a different action than the LLM's first suggestion.

Storage: ``~/.neuro_os_skillified/events.jsonl`` (append-only).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


VerticalName = Literal["founder_loop", "research", "investment", "startup"]


class OverrideEvent(BaseModel):
    """One row in the override log.

    Frozen — once written, the event is immutable. The audit trail is
    the value: pattern extraction reads the events and proposes a new
    ConstructiveExpression candidate, but never mutates the events
    themselves.
    """

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(min_length=1, max_length=128)
    ts: datetime
    vertical: VerticalName
    drift_mode: str = Field(
        min_length=1, max_length=64,
        description="The named drift mode that fired (must match the "
                    "vertical's catalog: paper_collector, topic_hopper, "
                    "etc.). Pattern extraction buckets by this field.",
    )
    suggested_action: Optional[str] = Field(
        default=None, max_length=400,
        description="What the substrate proposed (the CE the user "
                    "rejected). Optional — the user may not always "
                    "remember, and the registry has it anyway.",
    )
    user_action: str = Field(
        min_length=1, max_length=400,
        description="What the user did instead. This is the load-bearing "
                    "field — pattern extraction looks for repeated "
                    "user_action text across ≥N events on the same drift "
                    "mode.",
    )
    notes: Optional[str] = Field(
        default=None, max_length=600,
        description="Optional one-paragraph explanation: why the user "
                    "chose this alternative.",
    )


def _events_path(home: Optional[Path] = None) -> Path:
    base = home or (Path.home() / ".neuro_os_skillified")
    return base / "events.jsonl"


def write_override_event(
    *,
    vertical: VerticalName,
    drift_mode: str,
    user_action: str,
    suggested_action: Optional[str] = None,
    notes: Optional[str] = None,
    home: Optional[Path] = None,
    ts: Optional[datetime] = None,
) -> OverrideEvent:
    """Append one OverrideEvent to ``~/.neuro_os_skillified/events.jsonl``.

    Atomic write: the line is buffered into a temp file, fsync'd, then
    appended via os.write so a crash mid-line doesn't corrupt the log.
    """
    when = ts or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    event = OverrideEvent(
        event_id=uuid.uuid4().hex[:16],
        ts=when,
        vertical=vertical,
        drift_mode=drift_mode,
        user_action=user_action,
        suggested_action=suggested_action,
        notes=notes,
    )
    path = _events_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = event.model_dump_json() + "\n"
    # Atomic append: write via a temp buffer + os.write to the open fd
    # so partial writes don't half-commit a row.
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        encoded = line.encode("utf-8")
        written = 0
        while written < len(encoded):
            n = os.write(fd, encoded[written:])
            if n <= 0:
                raise OSError("os.write returned 0 — disk full?")
            written += n
        os.fsync(fd)
    finally:
        os.close(fd)
    return event


def read_override_events(
    *,
    home: Optional[Path] = None,
    vertical: Optional[VerticalName] = None,
    drift_mode: Optional[str] = None,
    since: Optional[datetime] = None,
) -> List[OverrideEvent]:
    """Read all events, optionally filtered. Skip malformed lines."""
    path = _events_path(home)
    if not path.exists():
        return []
    out: List[OverrideEvent] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = OverrideEvent.model_validate_json(line)
            except Exception:
                continue
            if vertical is not None and event.vertical != vertical:
                continue
            if drift_mode is not None and event.drift_mode != drift_mode:
                continue
            if since is not None:
                ts = event.ts
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                since_aware = since if since.tzinfo else since.replace(
                    tzinfo=timezone.utc
                )
                if ts < since_aware:
                    continue
            out.append(event)
    return out


__all__ = [
    "VerticalName",
    "OverrideEvent",
    "write_override_event",
    "read_override_events",
]
