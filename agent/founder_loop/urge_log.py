"""
``urge_log.py`` — first-class user-reported urge events.

The original loop is *passive*: ``observe.py`` reads workflowx exports,
``predict.py`` infers ``predicted_urge``, and ``policy.py`` acts on the
forecast. That's the right model when sensors are reliable, but for v0
it leaves the user without an explicit "I want YouTube right now" lever
— the policy has to wait for the predictor to catch up.

This module fills that gap. The user calls ``log_urge_event`` (via
``loop urge`` CLI or ``FounderLoop.log_urge``) to record a real urge as
it fires. Subsequent ticks honor the user-logged urge as ground truth
over the predictor's guess (see ``policy.decide_control``).

Storage shape: append-only JSONL at ``founder_events.jsonl``. Two row
kinds:

* ``{"kind": "urge", ...}`` — an urge fired.
* ``{"kind": "urge_resolution", "urge_id": "...", "resolved_with": "..."}`` —
  the urge was resolved (constructive expression accepted, override fired,
  user explicitly cleared, etc.).

``read_recent_urge`` folds resolutions into urges so callers see a
single ``UrgeEvent`` with ``resolved_at`` populated when applicable.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

from agent.founder_loop.state import UrgeType


_URGE_CONTEXT_MAX = 400

# Default daily rate limit on user-logged urges. The point isn't to
# stop the user from reporting urges (the loop wants the data); it's
# to guarantee Law 6's rejection rule has a concrete trigger. Without
# a cap, a panicked user could write thousands of rows per second, the
# 'most recent' lookup degenerates, and the daemon has no signal that
# something's wrong. 5/day is generous for normal use and still
# catches the pathological case.
_DEFAULT_DAILY_CAP = 5


class RateLimitExceeded(RuntimeError):
    """Raised by ``log_urge_event`` when the daily cap is exceeded.

    Carries the cap and the count for clear error messages. Callers
    (CLI, browser extension) should surface this to the user — Law 6's
    rejection rule says the system must say no out loud, not silently
    deny.
    """

    def __init__(self, *, cap: int, count: int, day: str) -> None:
        super().__init__(
            f"daily urge cap exceeded: {count} urges already logged on "
            f"{day}, cap is {cap}/day. To raise the cap, set the "
            f"FOUNDER_LOOP_URGE_DAILY_CAP env var or pass "
            f"daily_cap=N to log_urge_event()."
        )
        self.cap = cap
        self.count = count
        self.day = day


UrgeSource = Literal["user_logged", "predicted"]
UrgeResolution = Literal[
    "constructive_accepted",  # user took the proposed alternative
    "override_proceeded",  # user proceeded to the distraction anyway
    "user_cleared",  # user dismissed without action
    "expired",  # auto-closed after window
]


class UrgeEvent(BaseModel):
    """A single urge-firing event reported by the user (or predicted).

    The ``source`` field distinguishes user-logged ground truth from
    predicted urges. v0 only writes ``user_logged`` from this module;
    predictions live on ``ForecastedState`` rather than here.
    """

    id: str = Field(min_length=1, max_length=32)
    ts: datetime
    urge_type: UrgeType
    source: UrgeSource = Field(default="user_logged")
    context: str = Field(default="", max_length=_URGE_CONTEXT_MAX)
    resolved_with: Optional[UrgeResolution] = Field(default=None)
    resolved_at: Optional[datetime] = Field(default=None)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _daily_cap_from_env(default: int = _DEFAULT_DAILY_CAP) -> int:
    """Read the daily cap from FOUNDER_LOOP_URGE_DAILY_CAP if set."""
    raw = os.environ.get("FOUNDER_LOOP_URGE_DAILY_CAP")
    if not raw:
        return default
    try:
        n = int(raw)
        if n < 1:
            return default
        return n
    except ValueError:
        return default


def _count_urges_on_day(path: Union[str, Path], day_iso: str) -> int:
    """Count user-logged urge rows whose ts starts with ``day_iso``."""
    p = Path(path)
    if not p.exists():
        return 0
    count = 0
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("kind") != "urge":
                continue
            if row.get("source") != "user_logged":
                continue
            ts = row.get("ts", "")
            if isinstance(ts, str) and ts.startswith(day_iso):
                count += 1
    return count


def log_urge_event(
    *,
    urge_type: UrgeType,
    context: str = "",
    path: Union[str, Path],
    ts: Optional[datetime] = None,
    source: UrgeSource = "user_logged",
    daily_cap: Optional[int] = None,
) -> UrgeEvent:
    """Append a new urge event to ``path``. Returns the created event.

    Raises ``RateLimitExceeded`` when the per-day cap has already been
    reached for this ``path`` on the same UTC day. The cap is
    enforced only for ``source="user_logged"`` rows — predictor-emitted
    rows aren't bound by the cap. Default cap: 5/day (configurable via
    ``daily_cap=N`` argument or ``FOUNDER_LOOP_URGE_DAILY_CAP`` env
    var).
    """
    ts = ts or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    if source == "user_logged":
        cap = daily_cap if daily_cap is not None else _daily_cap_from_env()
        day_iso = ts.date().isoformat()
        existing = _count_urges_on_day(path, day_iso)
        if existing >= cap:
            raise RateLimitExceeded(cap=cap, count=existing, day=day_iso)

    event = UrgeEvent(
        id=_new_id(),
        ts=ts,
        urge_type=urge_type,
        source=source,
        context=(context or "")[:_URGE_CONTEXT_MAX],
    )
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"kind": "urge", **json.loads(event.model_dump_json())}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return event


def resolve_urge(
    *,
    urge_id: str,
    resolved_with: UrgeResolution,
    path: Union[str, Path],
    ts: Optional[datetime] = None,
) -> None:
    """Append a resolution row referencing ``urge_id``.

    No-op when the file doesn't exist or the id doesn't match a prior
    urge — callers shouldn't depend on this rejecting bad ids; the
    join in ``read_recent_urge`` simply ignores orphan resolutions.
    """
    ts = ts or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "kind": "urge_resolution",
        "urge_id": urge_id,
        "resolved_with": resolved_with,
        "resolved_at": ts.isoformat(),
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _read_rows(path: Union[str, Path]) -> List[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows: List[dict] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def read_urges(path: Union[str, Path]) -> List[UrgeEvent]:
    """Return all urge events, with resolutions folded in, in append order."""
    rows = _read_rows(path)
    urges: dict[str, UrgeEvent] = {}
    order: List[str] = []
    for row in rows:
        kind = row.get("kind")
        if kind == "urge":
            try:
                ev = UrgeEvent.model_validate(
                    {k: v for k, v in row.items() if k != "kind"}
                )
            except Exception:
                continue
            urges[ev.id] = ev
            order.append(ev.id)
        elif kind == "urge_resolution":
            uid = row.get("urge_id")
            if not uid or uid not in urges:
                continue
            try:
                resolved_at = datetime.fromisoformat(row["resolved_at"])
            except (KeyError, TypeError, ValueError):
                continue
            ev = urges[uid]
            urges[uid] = ev.model_copy(
                update={
                    "resolved_with": row.get("resolved_with"),
                    "resolved_at": resolved_at,
                }
            )
    return [urges[i] for i in order]


def read_recent_urge(
    path: Union[str, Path],
    *,
    since: Optional[datetime] = None,
    window_minutes: int = 15,
    only_unresolved: bool = True,
    now: Optional[datetime] = None,
) -> Optional[UrgeEvent]:
    """Most recent urge newer than ``since`` (default: now - window_minutes).

    When ``only_unresolved=True`` (the default — what the policy wants),
    skips urges with a non-None ``resolved_at``.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = since or (now - timedelta(minutes=window_minutes))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)

    candidates = read_urges(path)
    candidates.sort(key=lambda e: e.ts, reverse=True)
    for ev in candidates:
        ts = ev.ts if ev.ts.tzinfo else ev.ts.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            return None
        if only_unresolved and ev.resolved_at is not None:
            continue
        return ev
    return None


__all__ = [
    "UrgeEvent",
    "UrgeSource",
    "UrgeResolution",
    "RateLimitExceeded",
    "log_urge_event",
    "resolve_urge",
    "read_urges",
    "read_recent_urge",
]
