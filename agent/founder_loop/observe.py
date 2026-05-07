"""
``observe.py`` — build a ``FounderState`` from a workflowx JSONL export.

Real-system shape: workflowx writes hourly JSONL events under
``~/Library/.../workflowx/exports/``. Each line is a ``RawEvent`` with
fields like ``{timestamp, distraction_minutes, deep_work_minutes,
context_switches, last_intent, ...}``. v0 doesn't yet have a workflowx
binding so we ship:

1. A ``RawEvent`` Pydantic schema that pins the contract.
2. A ``WorkflowxAdapter`` interface with a single method
   ``read_window(start, end)`` that returns ``list[RawEvent]``.
3. A concrete ``FixtureWorkflowxAdapter`` that reads the same shape from
   a JSONL file — used for tests and the dry-run example.
4. ``build_founder_state(events, ...)`` — the pure-function reduce that
   produces a ``FounderState`` from a window of raw events.

The adapter interface means swapping the fixture for a live binding is
zero changes to the rest of the loop.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Protocol, Union

from pydantic import BaseModel, Field

from agent.founder_loop.state import FounderState


# ---------------------------------------------------------------------------
# Raw event schema (the workflowx contract)
# ---------------------------------------------------------------------------


class RawEvent(BaseModel):
    """A single raw event row as workflowx writes it.

    Adapters return a list of these from ``read_window``. ``observe``
    folds them into a single ``FounderState`` per-hour.
    """

    timestamp: datetime
    distraction_minutes: float = Field(default=0.0, ge=0.0)
    deep_work_minutes: float = Field(default=0.0, ge=0.0)
    context_switches: int = Field(default=0, ge=0)

    # Optional embodied / social signals — workflowx may or may not
    # report these depending on the user's instrument coverage.
    sleep_last_night_hours: Optional[float] = None
    minutes_since_last_meal: Optional[int] = None
    hours_continuous_screen: Optional[float] = None
    last_outbound_message_age_h: Optional[float] = None

    # Intent capture — most recent free-text intent the user wrote.
    last_intent: Optional[str] = None

    # Day-shape hint — workflowx looks at the calendar / a special tag.
    day_kind: Optional[str] = None

    @classmethod
    def from_jsonl_line(cls, line: str) -> "RawEvent":
        return cls.model_validate(json.loads(line))


# ---------------------------------------------------------------------------
# Adapter interface
# ---------------------------------------------------------------------------


class WorkflowxAdapter(Protocol):
    """Read raw events for a window. Implementations: live + fixture."""

    def read_window(
        self, start: datetime, end: datetime
    ) -> List[RawEvent]:  # pragma: no cover - interface only
        ...


class FixtureWorkflowxAdapter:
    """Reads RawEvents from a JSONL file. Used for tests + dry-runs.

    The fixture is the *whole* file; ``read_window`` filters by
    timestamp. Each UAT scenario gets its own fixture file under
    ``tests/fixtures/founder_loop/``.
    """

    def __init__(self, fixture_path: Union[str, Path]) -> None:
        self.fixture_path = Path(fixture_path)
        self._cache: Optional[List[RawEvent]] = None

    def _load(self) -> List[RawEvent]:
        if self._cache is not None:
            return self._cache
        events: List[RawEvent] = []
        if self.fixture_path.exists():
            with self.fixture_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(RawEvent.from_jsonl_line(line))
                    except Exception:
                        # Malformed line — skip silently. Workflowx
                        # is an external sensor; partial corruption
                        # (bad JSON, missing fields, wrong types)
                        # shouldn't take down the loop. Surfaces in
                        # e2e scenario S15.
                        continue
        events.sort(key=lambda e: e.timestamp)
        self._cache = events
        return events

    def read_window(self, start: datetime, end: datetime) -> List[RawEvent]:
        events = self._load()
        return [e for e in events if start <= e.timestamp <= end]

    def all_events(self) -> List[RawEvent]:
        """Convenience for tests + the dry-run example."""
        return list(self._load())


# ---------------------------------------------------------------------------
# Reduce raw events → FounderState
# ---------------------------------------------------------------------------


_REST_DAY_RE = re.compile(r"\b(rest|off|holiday|recover|recovering|break|sabbath)\b", re.IGNORECASE)
_SHIP_DAY_RE = re.compile(r"\b(ship|launch|deploy|release)\b", re.IGNORECASE)


def _infer_day_kind(events: Iterable[RawEvent]) -> str:
    """Look at the most recent ``last_intent`` and the explicit
    ``day_kind`` hint to decide the day-shape.

    Explicit ``day_kind`` from the adapter wins. Otherwise we regex
    the most recent intent for rest-day / ship-day language. UAT
    scenario #7 ("user types 'rest day'") drives off this.
    """
    most_recent_kind = None
    most_recent_intent = None
    for e in events:
        if e.day_kind:
            most_recent_kind = e.day_kind
        if e.last_intent:
            most_recent_intent = e.last_intent
    if most_recent_kind in ("work", "rest", "ship"):
        return most_recent_kind
    if most_recent_intent:
        if _REST_DAY_RE.search(most_recent_intent):
            return "rest"
        if _SHIP_DAY_RE.search(most_recent_intent):
            return "ship"
    return "unspecified"


def build_founder_state(
    events: List[RawEvent],
    *,
    now: datetime,
    rolling_7d_events: Optional[List[RawEvent]] = None,
) -> FounderState:
    """Fold a window of raw events into a single ``FounderState``.

    ``events`` is the last-hour window. ``rolling_7d_events`` is the
    optional 7-day window used to compute the rolling means for the
    ``*_7d_avg`` fields. When ``None``, those fields are left blank.

    The most recent event's optional fields (sleep, meal, screen,
    social, intent) are forwarded onto the resulting state. Rate
    quantities (distraction, deep work, switches) are summed across the
    whole hour, then clipped to [0, 60] / int.
    """
    if not events:
        # No observations — return a sentinel-like state with zeros so
        # the dead-sensor golden (#8) can fire.
        return FounderState(
            timestamp=now,
            distraction_minutes_last_hour=0.0,
            deep_work_minutes_last_hour=0.0,
            context_switches_last_hour=0,
            sleep_last_night_hours=None,
            time_since_last_meal_min=None,
            hours_continuous_screen=None,
            last_outbound_message_age_h=None,
            distraction_7d_avg=None,
            deep_work_7d_avg=None,
            last_intent=None,
            day_kind="unspecified",
        )

    distraction = sum(e.distraction_minutes for e in events)
    deep_work = sum(e.deep_work_minutes for e in events)
    switches = sum(e.context_switches for e in events)

    # Use the most recent event's "current state" fields.
    last = max(events, key=lambda e: e.timestamp)

    distraction_7d_avg: Optional[float] = None
    deep_work_7d_avg: Optional[float] = None
    if rolling_7d_events:
        # Per-hour means: divide by the hour count in the window. We
        # approximate hours as ceil((end-start)/3600) which works for
        # the common case of one event per hour.
        if len(rolling_7d_events) > 0:
            distraction_7d_avg = (
                sum(e.distraction_minutes for e in rolling_7d_events)
                / len(rolling_7d_events)
            )
            deep_work_7d_avg = (
                sum(e.deep_work_minutes for e in rolling_7d_events)
                / len(rolling_7d_events)
            )

    return FounderState(
        timestamp=now,
        distraction_minutes_last_hour=min(60.0, max(0.0, distraction)),
        deep_work_minutes_last_hour=min(60.0, max(0.0, deep_work)),
        context_switches_last_hour=max(0, int(switches)),
        sleep_last_night_hours=last.sleep_last_night_hours,
        time_since_last_meal_min=last.minutes_since_last_meal,
        hours_continuous_screen=last.hours_continuous_screen,
        last_outbound_message_age_h=last.last_outbound_message_age_h,
        distraction_7d_avg=distraction_7d_avg,
        deep_work_7d_avg=deep_work_7d_avg,
        last_intent=last.last_intent,
        day_kind=_infer_day_kind(events),
    )


def observe(
    adapter: WorkflowxAdapter,
    *,
    now: datetime,
    window_minutes: int = 60,
    include_7d_avg: bool = True,
) -> FounderState:
    """End-to-end: read the last hour from the adapter and reduce.

    When ``include_7d_avg=True``, also reads the previous 7 days for the
    rolling-avg fields. Set ``False`` for tests that don't need history.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    window_start = now - timedelta(minutes=window_minutes)
    events = adapter.read_window(window_start, now)

    rolling_7d: Optional[List[RawEvent]] = None
    if include_7d_avg:
        rolling_7d = adapter.read_window(now - timedelta(days=7), now)

    return build_founder_state(events, now=now, rolling_7d_events=rolling_7d)


__all__ = [
    "RawEvent",
    "WorkflowxAdapter",
    "FixtureWorkflowxAdapter",
    "build_founder_state",
    "observe",
]
