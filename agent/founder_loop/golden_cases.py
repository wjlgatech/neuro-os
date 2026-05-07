"""
``founder_loop`` golden cases — falsifiability gate for the loop itself.

Mirrors the L1-pattern from ``agent/personal_epistemic_domain.py``: a
fixed set of "if THIS happens, the loop is broken" cases. The nightly
summarizer evaluates the last 24h against these. When ≥2 fail in a 7-day
window, the summarizer's ``action`` flips from ``update_contract`` to
``rebuild_predictor`` or ``rebuild_sublimation_catalog`` depending on
which goldens fired.

Each golden has:

* ``name`` — stable identifier; appears in ``NightlySummary.goldens_failed``.
* ``predicate(rows: list[dict]) -> bool`` — pure function over the last
  N registry rows. Returns True iff the golden has *fired* (i.e. the
  loop is broken).
* ``rebuilds`` — which subsystem the trigger should rewrite:
  ``"predictor"``, ``"sublimation_catalog"``, or
  ``"morning_ritual_prompt"``.
* ``description`` — human-readable for the night-summary report.

Predicates take "rows" as the JSONL-decoded list of registry entries
(dicts) sorted oldest → newest. Each row is the dict written by
``memory.append_registry_row()``: ``{state, forecasted, tank, action,
contract_check, mae_hourly, ...}``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Literal, Optional


RebuildTarget = Literal[
    "predictor",
    "sublimation_catalog",
    "morning_ritual_prompt",
    "none",
]


@dataclass(frozen=True)
class GoldenCase:
    name: str
    predicate: Callable[[List[Dict]], bool]
    rebuilds: RebuildTarget
    description: str


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def _morning_overconfidence(rows: List[Dict]) -> bool:
    """predicted < 30min ∧ actual > 90min distraction in any morning hour.

    "Morning" = local hour 6–11 inclusive. We don't have local-tz on
    every row in v0, so approximate via the row's ``state.timestamp``
    UTC hour. A real installation will set TZ via the config file.
    """
    for row in rows:
        state = row.get("state") or {}
        forecasted = row.get("forecasted") or {}
        ts = state.get("timestamp")
        try:
            hour = datetime.fromisoformat(ts).hour if ts else None
        except (TypeError, ValueError):
            hour = None
        if hour is None or not (6 <= hour <= 11):
            continue
        predicted = float(forecasted.get("predicted_distraction_min", 0.0) or 0.0)
        actual = float(state.get("distraction_minutes_last_hour", 0.0) or 0.0)
        if predicted < 30.0 and actual > 90.0:
            return True
    return False


def _missing_need_in_catalog(rows: List[Dict]) -> bool:
    """``predicted_underlying_need == 'none'`` AND actual distraction > 45min.

    The predictor said "no urge incoming, no need to diagnose," and yet
    the user spent >45min distracted. The catalog is missing whatever
    need was actually firing.
    """
    for row in rows:
        forecasted = row.get("forecasted") or {}
        state = row.get("state") or {}
        if forecasted.get("predicted_underlying_need") != "none":
            continue
        actual = float(state.get("distraction_minutes_last_hour", 0.0) or 0.0)
        if actual > 45.0:
            return True
    return False


def _delusional_intent_capture(rows: List[Dict]) -> bool:
    """predicted_deep_work > 45 ∧ actual_deep_work < 15 for 2 consecutive ticks."""
    consecutive = 0
    for row in rows:
        state = row.get("state") or {}
        forecasted = row.get("forecasted") or {}
        predicted = float(forecasted.get("predicted_deep_work_min", 0.0) or 0.0)
        actual = float(state.get("deep_work_minutes_last_hour", 0.0) or 0.0)
        if predicted > 45.0 and actual < 15.0:
            consecutive += 1
            if consecutive >= 2:
                return True
        else:
            consecutive = 0
    return False


def _model_drift(rows: List[Dict]) -> bool:
    """MAE on the last 24h doubled vs the previous 24h."""
    if len(rows) < 48:
        return False
    last_24 = rows[-24:]
    prev_24 = rows[-48:-24]

    def _mae(window: List[Dict]) -> float:
        errors = []
        for row in window:
            state = row.get("state") or {}
            forecasted = row.get("forecasted") or {}
            predicted = forecasted.get("predicted_distraction_min")
            actual = state.get("distraction_minutes_last_hour")
            if predicted is None or actual is None:
                continue
            errors.append(abs(float(predicted) - float(actual)))
        return sum(errors) / len(errors) if errors else 0.0

    mae_last = _mae(last_24)
    mae_prev = _mae(prev_24)
    if mae_prev <= 0.0:
        return False
    return mae_last >= 2.0 * mae_prev


def _contract_too_aggressive(rows: List[Dict]) -> bool:
    """Contract-honor rate < 0.5 for 3 consecutive days.

    When the contract is too tight, today-self overrides it constantly.
    The fix is to rewrite the morning-ritual prompt to suggest fewer
    priorities or a longer ration, not to punish today-self harder.
    """
    by_day: Dict[str, List[bool]] = {}
    for row in rows:
        state = row.get("state") or {}
        ts = state.get("timestamp", "")
        day = ts[:10] if ts else ""
        check = row.get("action", {}).get("contract_check") or row.get("contract_check") or {}
        honored = bool(check.get("honored", True))
        by_day.setdefault(day, []).append(honored)

    days_sorted = sorted(by_day.keys())
    if len(days_sorted) < 3:
        return False
    consecutive_low = 0
    for day in days_sorted:
        flags = by_day[day]
        if not flags:
            consecutive_low = 0
            continue
        rate = sum(1 for h in flags if h) / len(flags)
        if rate < 0.5:
            consecutive_low += 1
            if consecutive_low >= 3:
                return True
        else:
            consecutive_low = 0
    return False


def _wrong_diagnosis_or_expression(rows: List[Dict]) -> bool:
    """≥3 consecutive ``propose_constructive_expression`` ops refused with same need.

    Refusal is signaled by a follow-up row where ``contract_check.honored=False``
    AND ``violation_type='threshold_violation'`` (the user opened
    entertainment despite the offered alternative). When the same
    underlying need produces this 3+ times in a row, that catalog entry
    is wrong — wrong diagnosis or wrong constructive expression.
    """
    streak: Optional[str] = None
    streak_len = 0
    for row in rows:
        action = row.get("action") or {}
        if action.get("op") != "propose_constructive_expression":
            streak = None
            streak_len = 0
            continue
        diagnosis = action.get("diagnosis") or {}
        need = diagnosis.get("underlying_need")
        check = action.get("contract_check") or {}
        refused = (
            not check.get("honored", True)
            and check.get("violation_type") == "threshold_violation"
        )
        if not refused:
            streak = None
            streak_len = 0
            continue
        if need == streak:
            streak_len += 1
            if streak_len >= 3:
                return True
        else:
            streak = need
            streak_len = 1
    return False


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


PERSONAL_GOLDEN_CASES: List[GoldenCase] = [
    GoldenCase(
        name="morning_overconfidence",
        predicate=_morning_overconfidence,
        rebuilds="predictor",
        description=(
            "Predicted < 30min distraction but actual > 90min in a "
            "morning hour. Predictor systematically underestimates."
        ),
    ),
    GoldenCase(
        name="missing_need_in_catalog",
        predicate=_missing_need_in_catalog,
        rebuilds="sublimation_catalog",
        description=(
            "Predictor said 'no underlying need' yet user was distracted "
            ">45min. The catalog is missing whatever need was firing."
        ),
    ),
    GoldenCase(
        name="delusional_intent_capture",
        predicate=_delusional_intent_capture,
        rebuilds="predictor",
        description=(
            "Predicted >45min deep work, actual <15min, two ticks in a "
            "row. Morning intent is unrealistic."
        ),
    ),
    GoldenCase(
        name="model_drift",
        predicate=_model_drift,
        rebuilds="predictor",
        description="MAE doubled in the last 24h vs the previous 24h.",
    ),
    GoldenCase(
        name="contract_too_aggressive",
        predicate=_contract_too_aggressive,
        rebuilds="morning_ritual_prompt",
        description=(
            "Contract-honor rate < 0.5 for 3 consecutive days — the "
            "contract is too tight. Suggest fewer priorities or longer "
            "ration in the morning ritual prompt."
        ),
    ),
    GoldenCase(
        name="wrong_diagnosis_or_expression",
        predicate=_wrong_diagnosis_or_expression,
        rebuilds="sublimation_catalog",
        description=(
            "Same underlying_need diagnosis refused with threshold "
            "violation 3+ times in a row. The catalog entry for that "
            "need is wrong."
        ),
    ),
]


def evaluate_goldens(rows: List[Dict]) -> List[GoldenCase]:
    """Return the subset of golden cases that fired against ``rows``."""
    return [g for g in PERSONAL_GOLDEN_CASES if g.predicate(rows)]


def choose_rebuild_target(failed: List[GoldenCase]) -> RebuildTarget:
    """Aggregate failed goldens into a single rebuild action.

    Priority: predictor > sublimation_catalog > morning_ritual_prompt.
    Rationale: a broken predictor poisons every other layer, so rebuild
    that first. Then the sublimation catalog (the philosophical heart).
    Then the morning ritual prompt.
    """
    if not failed:
        return "none"
    targets = {g.rebuilds for g in failed}
    for priority in ("predictor", "sublimation_catalog", "morning_ritual_prompt"):
        if priority in targets:
            return priority  # type: ignore[return-value]
    return "none"


__all__ = [
    "GoldenCase",
    "RebuildTarget",
    "PERSONAL_GOLDEN_CASES",
    "evaluate_goldens",
    "choose_rebuild_target",
]
