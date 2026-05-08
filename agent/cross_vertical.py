"""
``cross_vertical`` — typed contract for one vertical to read another's outputs.

Each vertical (research / investment / startup / founder_loop) writes
``VerticalNote`` rows to a shared per-user store. Other verticals can
query the store, but **only see notes whose ``visible_to`` list
includes their vertical_name**.

## Visibility default: PRIVATE

Per the Phase 0 design decision (sensitive data — investment
positions, startup confidentials, research IP), every note is
**private to its source vertical by default**. Sharing requires
explicit user opt-in:

* Per-note: pass ``visible_to=["investment", "research"]`` at write
  time.
* Per-vertical default-policy: each vertical's ``DomainConfig`` MAY
  set a different default ``visibility_policy`` (e.g. research could
  default to "all" if the user signs a privacy waiver), but THIS
  module always honors the per-note ``visible_to`` if set.

## Storage shape

Single append-only JSONL at ``~/.neuro_os/cross_vertical.jsonl``
(gitignored, local-only). Each row:

    {
      "id": "<short-uuid>",
      "source_vertical": "investment",
      "note_kind": "position_thesis",
      "payload": {...},
      "ts": "<iso8601>",
      "visible_to": ["investment"]   # default = source only
    }

## API

* ``write_note(...)``  — append a typed note.
* ``query(reader, ...)``  — read notes the reader is allowed to see.
* ``share_note(id, with=...)``  — broaden a note's ``visible_to``
  list after the fact (audit-trailed).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# Substrate-level vocabulary. Verticals MUST declare their name here.
VerticalName = Literal["founder_loop", "research", "investment", "startup"]


_VISIBILITY_ALL = "__all__"


def default_store_path() -> Path:
    """Where the cross-vertical store lives on the local machine.

    Honors ``NEURO_OS_HOME`` env var for testing/relocation. Default:
    ``~/.neuro_os/cross_vertical.jsonl``.
    """
    base = os.environ.get("NEURO_OS_HOME")
    if base:
        return Path(base).expanduser() / "cross_vertical.jsonl"
    return Path.home() / ".neuro_os" / "cross_vertical.jsonl"


class VerticalNote(BaseModel):
    """One vertical's output, another's potential input.

    Frozen so the audit trail can't be mutated post-write.
    ``visible_to`` is the visibility allowlist; default is
    ``[<source_vertical>]`` (private). Special value ``"__all__"``
    means visible to every vertical (the user broadens explicitly).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    source_vertical: VerticalName
    note_kind: str = Field(
        min_length=1,
        max_length=64,
        description=(
            "Vertical-specific kind label. Examples: 'mechanism_card' "
            "(research), 'position_thesis' (investment), "
            "'startup_hypothesis' (startup), 'priority' (founder_loop)."
        ),
    )
    payload: Dict[str, Any] = Field(
        description="The note's content. Verticals validate the shape."
    )
    ts: datetime
    visible_to: List[str] = Field(
        description=(
            "Allowlist of vertical names that can read this note. "
            "Defaults to [source_vertical] (private). Use "
            "['__all__'] for cross-vertical visible."
        ),
    )

    def is_visible_to(self, reader: VerticalName) -> bool:
        """Check whether ``reader`` is allowed to see this note."""
        if reader == self.source_vertical:
            return True  # source can always read its own
        if _VISIBILITY_ALL in self.visible_to:
            return True
        return reader in self.visible_to


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def write_note(
    *,
    source_vertical: VerticalName,
    note_kind: str,
    payload: Dict[str, Any],
    visible_to: Optional[List[str]] = None,
    store: Optional[Union[str, Path]] = None,
    ts: Optional[datetime] = None,
) -> VerticalNote:
    """Append a typed note to the cross-vertical store.

    Default ``visible_to`` is ``[source_vertical]`` (private). Pass
    ``['__all__']`` or a specific list of vertical names to broaden.
    """
    ts = ts or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if visible_to is None:
        visible_to = [source_vertical]

    note = VerticalNote(
        id=_new_id(),
        source_vertical=source_vertical,
        note_kind=note_kind,
        payload=payload,
        ts=ts,
        visible_to=visible_to,
    )

    path = Path(store) if store is not None else default_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"kind": "note", **json.loads(note.model_dump_json())}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return note


def share_note(
    *,
    note_id: str,
    add_visible: List[str],
    store: Optional[Union[str, Path]] = None,
    ts: Optional[datetime] = None,
) -> None:
    """Broaden a note's visibility AFTER write.

    Appends a ``share_event`` row referencing the original note id.
    The original note row is NOT mutated (immutable audit trail).
    Reads via ``query`` fold these events on top of the original.
    """
    ts = ts or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    path = Path(store) if store is not None else default_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "kind": "share_event",
        "note_id": note_id,
        "add_visible": add_visible,
        "ts": ts.isoformat(),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
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


def query(
    *,
    reader: VerticalName,
    kinds: Optional[List[str]] = None,
    sources: Optional[List[VerticalName]] = None,
    since: Optional[datetime] = None,
    store: Optional[Union[str, Path]] = None,
) -> List[VerticalNote]:
    """Return notes the ``reader`` is allowed to see.

    Filters:
    * ``kinds`` — only return notes with these ``note_kind`` values.
    * ``sources`` — only notes from these source verticals.
    * ``since`` — only notes with ``ts >= since``.

    Visibility is enforced AFTER all filters: a note that matches
    every filter but isn't visible to ``reader`` is dropped.
    """
    path = Path(store) if store is not None else default_store_path()
    rows = _read_rows(path)

    # First pass: load notes by id.
    notes: Dict[str, VerticalNote] = {}
    order: List[str] = []
    for row in rows:
        if row.get("kind") == "note":
            try:
                note = VerticalNote.model_validate(
                    {k: v for k, v in row.items() if k != "kind"}
                )
            except Exception:
                continue
            notes[note.id] = note
            order.append(note.id)

    # Second pass: apply share_event broadenings.
    for row in rows:
        if row.get("kind") == "share_event":
            note_id = row.get("note_id")
            if note_id and note_id in notes:
                add = row.get("add_visible", [])
                if isinstance(add, list):
                    cur = notes[note_id]
                    new_visible = list(cur.visible_to) + [
                        v for v in add if v not in cur.visible_to
                    ]
                    notes[note_id] = cur.model_copy(
                        update={"visible_to": new_visible}
                    )

    # Filter + visibility check.
    out: List[VerticalNote] = []
    for nid in order:
        note = notes[nid]
        if kinds and note.note_kind not in kinds:
            continue
        if sources and note.source_vertical not in sources:
            continue
        if since is not None:
            ts = note.ts
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            since_aware = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
            if ts < since_aware:
                continue
        if not note.is_visible_to(reader):
            continue
        out.append(note)
    return out


__all__ = [
    "VerticalNote",
    "VerticalName",
    "default_store_path",
    "write_note",
    "share_note",
    "query",
]
