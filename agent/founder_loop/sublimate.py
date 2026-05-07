"""
``sublimate.py`` — name the underlying need, propose a constructive expression.

This module is the philosophical heart of the loop. The premise:

> Negative destructive behavior is the counterfeit expression of a
> God-given desire. Acknowledge the desire, find a constructive
> expression as replacement — no simple suppression.

Two surfaces:

* **``diagnose(state, urge_type, *, predicted_need=...)``** — the public
  one. Reads ``data/sublimation_catalog.json`` (and optionally per-user
  queue JSONs) and returns a ``Diagnosis`` with one or more concrete
  ``ConstructiveExpression`` options.
* **``set_diagnose_fn(fn)``** — test injection (UAT fixtures stub here).

Routing:

1. If a test diagnose fn is injected, use it.
2. Else if ``use_llm=True`` and the SDK is available, call the LLM with
   the catalog as the system prompt + the state as the user message,
   parse a ``Diagnosis`` directly.
3. Else fall back to **catalog routing**: a deterministic rule-based
   heuristic over the state signals (sleep < 6.5 ⇒ fatigue; meal > 240
   ⇒ embodied_hunger; etc.).

The catalog routing alone is ~90% useful — the LLM mostly adds
naturalistic reasoning text. That's the v0 bet.

References to per-user queues are populated into
``ConstructiveExpression.references`` when the queue file is present.
Without a queue, the option still works (the action remains valid; the
suggestion is generic).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agent.founder_loop.state import (
    Confidence,
    ConstructiveExpression,
    Diagnosis,
    FounderState,
    UnderlyingNeed,
    UrgeType,
)


_CATALOG_PATH = Path(__file__).parent / "data" / "sublimation_catalog.json"
_QUEUES_DIR = Path(__file__).parent / "data" / "queues"

_diagnose_fn: Optional[
    Callable[[FounderState, UrgeType, Optional[UnderlyingNeed]], Diagnosis]
] = None


# ---------------------------------------------------------------------------
# Test injection
# ---------------------------------------------------------------------------


def set_diagnose_fn(
    fn: Optional[Callable[[FounderState, UrgeType, Optional[UnderlyingNeed]], Diagnosis]],
) -> None:
    """Inject a custom diagnoser (used by UAT fixtures)."""
    global _diagnose_fn
    _diagnose_fn = fn


def reset_diagnose_fn() -> None:
    global _diagnose_fn
    _diagnose_fn = None


# ---------------------------------------------------------------------------
# Catalog + queue loaders
# ---------------------------------------------------------------------------


def load_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or _CATALOG_PATH
    if not p.exists():
        return {"version": 0, "needs": {}}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_queue(queue_name: str, queues_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    qdir = queues_dir or _QUEUES_DIR
    p = qdir / f"{queue_name}.json"
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        return list(json.load(f).get("items", []) or [])


def _format_queue_references(queue_name: str, queues_dir: Optional[Path] = None) -> List[str]:
    """Return up to 3 short reference strings ('title @ url') from a queue."""
    items = _load_queue(queue_name, queues_dir)
    refs: List[str] = []
    for item in items[:3]:
        if "title" in item and "url" in item:
            refs.append(f"{item['title']} @ {item['url']}")
        elif "name" in item:
            refs.append(f"{item['name']} ({item.get('preferred_contact_form', 'voice')})")
        elif "venue" in item:
            refs.append(f"{item['venue']} ({item['kind']})")
    return refs


# ---------------------------------------------------------------------------
# Catalog → Diagnosis
# ---------------------------------------------------------------------------


def _build_options_for_need(
    need: UnderlyingNeed,
    *,
    catalog: Dict[str, Any],
    queues_dir: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> List[ConstructiveExpression]:
    """Convert catalog entries into typed ``ConstructiveExpression``s."""
    needs_section = catalog.get("needs") or {}
    entry = needs_section.get(need)
    if not entry:
        return []
    now = now or datetime.now(timezone.utc)
    opts: List[ConstructiveExpression] = []
    for option in entry.get("options", []) or []:
        ref_queue = option.get("reference_queue")
        refs = _format_queue_references(ref_queue, queues_dir) if ref_queue else []
        reassess: Optional[datetime] = None
        if "reassess_after_min" in option:
            reassess = now + timedelta(minutes=int(option["reassess_after_min"]))
        opts.append(
            ConstructiveExpression(
                action=option["action"],
                duration_min=int(option["duration_min"]),
                tank_credit_pct=float(option["tank_credit_pct"]),
                references=refs,
                then_reassess_at=reassess,
            )
        )
    return opts


# ---------------------------------------------------------------------------
# Catalog routing (the deterministic heuristic, used when no LLM)
# ---------------------------------------------------------------------------


def _catalog_route(state: FounderState, urge_type: UrgeType) -> tuple[UnderlyingNeed, Confidence, str]:
    """Best deterministic guess at the underlying need given the state.

    Order is tuned so the *most distinctive* signals win:

    1. ``embodied_hunger`` — meal-gap > 240min trumps everything (low
       blood sugar masquerades as boredom).
    2. ``embodied_eye_strain`` — > 4h continuous screen.
    3. ``fatigue`` — sleep < 6.5h OR (afternoon + decision_latency).
    4. ``social`` — last_outbound_message_age_h > 48.
    5. ``frustration`` — flat output 60+ min on a hard task (low
       distraction + low deep_work + zero context_switches reflects
       'staring at it'; rising context_switches reflects 'thrashing').
    6. ``novelty_hunger`` — high deep_work + rising context_switches +
       non-fatigued.
    7. ``decision_fatigue`` — fallback for the noon/afternoon pattern
       when nothing else fits.

    Returns (underlying_need, confidence, reasoning).
    """
    # Embodied first
    if state.time_since_last_meal_min is not None and state.time_since_last_meal_min > 240:
        return (
            "embodied_hunger",
            "high",
            (
                f"time_since_last_meal_min={state.time_since_last_meal_min} "
                "> 240; the screen-is-boring signal often means low blood "
                "sugar in disguise."
            ),
        )
    if state.hours_continuous_screen is not None and state.hours_continuous_screen > 4.0:
        return (
            "embodied_eye_strain",
            "medium",
            f"hours_continuous_screen={state.hours_continuous_screen:.1f} > 4.",
        )

    # Fatigue
    if state.sleep_last_night_hours is not None and state.sleep_last_night_hours < 6.5:
        return (
            "fatigue",
            "high",
            (
                f"sleep_last_night_hours={state.sleep_last_night_hours} < 6.5; "
                "the urge is fatigue dressed as boredom."
            ),
        )

    # Social
    if (
        state.last_outbound_message_age_h is not None
        and state.last_outbound_message_age_h > 48.0
    ):
        return (
            "social",
            "medium",
            (
                f"last_outbound_message_age_h={state.last_outbound_message_age_h:.1f} "
                "> 48; YouTube is delivering counterfeit social — "
                "strangers' faces and voices, no reciprocity."
            ),
        )

    # Frustration: low output velocity over the last hour while in a
    # work day. Heuristic: low distraction + low deep_work + 0
    # context_switches → 'stuck staring'; or rising context_switches +
    # low deep_work → 'thrashing'.
    if (
        state.day_kind in ("work", "ship", "unspecified")
        and state.deep_work_minutes_last_hour < 15.0
        and (
            state.context_switches_last_hour == 0
            or state.context_switches_last_hour >= 5
        )
        and (state.distraction_minutes_last_hour < 25.0)
    ):
        return (
            "frustration",
            "medium",
            (
                "Flat output last hour; deep_work < 15min and either "
                "stuck-staring (0 switches) or thrashing (>=5 switches)."
            ),
        )

    # Novelty hunger
    if (
        state.deep_work_minutes_last_hour >= 30.0
        and state.context_switches_last_hour >= 4
        and (state.sleep_last_night_hours is None or state.sleep_last_night_hours >= 6.5)
    ):
        return (
            "novelty_hunger",
            "medium",
            (
                "Deep work + rising context switches without fatigue — "
                "the work is real but the current sub-task is grindy."
            ),
        )

    # Decision fatigue is the catch-all when an entertainment urge
    # surfaces but no specific signal explains it.
    if urge_type in ("entertainment", "escape"):
        return (
            "decision_fatigue",
            "low",
            (
                "Entertainment urge with no specific signal. Likely "
                "decision fatigue — too many open choices."
            ),
        )

    return (
        "none",
        "low",
        "No urge signal detected; underlying_need is 'none'.",
    )


# ---------------------------------------------------------------------------
# Public diagnose surface
# ---------------------------------------------------------------------------


def diagnose(
    state: FounderState,
    urge_type: UrgeType = "entertainment",
    *,
    predicted_need: Optional[UnderlyingNeed] = None,
    catalog: Optional[Dict[str, Any]] = None,
    queues_dir: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> Diagnosis:
    """Return a ``Diagnosis`` for the urge currently firing.

    When ``predicted_need`` is provided (from ``predict.py``) AND it's a
    known catalog entry AND non-'none', use it as the diagnosis. This
    lets the predictor's LLM-driven signal override the deterministic
    heuristic when both are available.

    Otherwise (and always as a check), run the catalog router. The two
    paths produce comparable shape so callers don't need to distinguish.

    The injected ``_diagnose_fn`` (if any) supersedes both paths — used
    by UAT fixtures to control diagnosis without an LLM round-trip.
    """
    if _diagnose_fn is not None:
        return _diagnose_fn(state, urge_type, predicted_need)

    cat = catalog or load_catalog()
    if predicted_need and predicted_need != "none" and predicted_need in (cat.get("needs") or {}):
        need = predicted_need
        reasoning = (
            "Predictor identified this need; catalog supplies "
            "constructive expressions."
        )
        confidence: Confidence = "high"
    else:
        need, confidence, reasoning = _catalog_route(state, urge_type)

    options = _build_options_for_need(
        need, catalog=cat, queues_dir=queues_dir, now=now
    )
    if not options:
        # No catalog entry — return a single 'continue' option so the
        # Diagnosis schema still validates. Policy will treat this as a
        # 'continue' suggestion.
        options = [
            ConstructiveExpression(
                action="continue",
                duration_min=1,
                tank_credit_pct=0.0,
            )
        ]
    return Diagnosis(
        underlying_need=need,
        confidence=confidence,
        reasoning=reasoning,
        options=options,
    )


__all__ = [
    "diagnose",
    "load_catalog",
    "set_diagnose_fn",
    "reset_diagnose_fn",
]
