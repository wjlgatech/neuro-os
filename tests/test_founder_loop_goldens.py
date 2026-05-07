"""Tests for ``agent.founder_loop.golden_cases``."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agent.founder_loop.golden_cases import (
    PERSONAL_GOLDEN_CASES,
    choose_rebuild_target,
    evaluate_goldens,
)


def _row(*, ts: datetime, distraction: float, predicted_distraction: float,
         predicted_need: str = "none", op: str = "continue", honored: bool = True,
         violation_type: str = None, deep_work: float = 30.0,
         predicted_deep: float = 30.0, diagnosis_need: str = None):
    state = {
        "timestamp": ts.isoformat(),
        "distraction_minutes_last_hour": distraction,
        "deep_work_minutes_last_hour": deep_work,
        "context_switches_last_hour": 0,
    }
    forecasted = {
        "predicted_distraction_min": predicted_distraction,
        "predicted_deep_work_min": predicted_deep,
        "predicted_underlying_need": predicted_need,
    }
    action = {"op": op, "contract_check": {"honored": honored}}
    if violation_type:
        action["contract_check"]["violation_type"] = violation_type
    if diagnosis_need:
        action["diagnosis"] = {"underlying_need": diagnosis_need}
    return {"state": state, "forecasted": forecasted, "action": action}


def test_morning_overconfidence_fires():
    rows = [_row(ts=datetime(2026, 5, 5, 9, tzinfo=timezone.utc),
                 distraction=95.0, predicted_distraction=20.0)]
    fired = evaluate_goldens(rows)
    assert any(g.name == "morning_overconfidence" for g in fired)
    assert choose_rebuild_target(fired) == "predictor"


def test_missing_need_in_catalog_fires():
    rows = [_row(ts=datetime(2026, 5, 5, 14, tzinfo=timezone.utc),
                 distraction=60.0, predicted_distraction=10.0,
                 predicted_need="none")]
    fired = evaluate_goldens(rows)
    assert any(g.name == "missing_need_in_catalog" for g in fired)


def test_delusional_intent_capture_fires_after_two_consecutive():
    base = datetime(2026, 5, 5, 10, tzinfo=timezone.utc)
    rows = [
        _row(ts=base, distraction=10, predicted_distraction=10,
             deep_work=5, predicted_deep=50),
        _row(ts=base + timedelta(hours=1), distraction=10, predicted_distraction=10,
             deep_work=10, predicted_deep=50),
    ]
    fired = evaluate_goldens(rows)
    assert any(g.name == "delusional_intent_capture" for g in fired)


def test_no_goldens_on_clean_data():
    base = datetime(2026, 5, 5, 9, tzinfo=timezone.utc)
    rows = [_row(ts=base + timedelta(hours=h),
                 distraction=15, predicted_distraction=14,
                 predicted_need="none", deep_work=30, predicted_deep=30)
            for h in range(8)]
    assert evaluate_goldens(rows) == []
    assert choose_rebuild_target([]) == "none"


def test_contract_too_aggressive_three_consecutive_low_days():
    """Use a shape that triggers ONLY contract_too_aggressive (no
    sublimation refusals) so the rebuild_target is morning_ritual_prompt.
    """
    rows = []
    for d in range(3):
        # 3 violations spread across diverse ops (so no single
        # underlying_need streak fires the catalog golden), and one
        # honored row per day.
        ts0 = datetime(2026, 5, 5 + d, 9, tzinfo=timezone.utc)
        rows.append(_row(ts=ts0, distraction=20, predicted_distraction=20,
                         op="continue", honored=True))
        # 3 distinct violation types/ops: this trips contract_too_aggressive
        # (rate < 0.5) but never 3-in-a-row of the same diagnosis.
        rows.append(_row(ts=ts0.replace(hour=10), distraction=20, predicted_distraction=20,
                         op="unlock_entertainment", honored=False,
                         violation_type="threshold_violation"))
        rows.append(_row(ts=ts0.replace(hour=11), distraction=20, predicted_distraction=20,
                         op="block_url", honored=False,
                         violation_type="block_target_not_authorized"))
        rows.append(_row(ts=ts0.replace(hour=12), distraction=20, predicted_distraction=20,
                         op="unlock_entertainment", honored=False,
                         violation_type="ration_violation"))
    fired = evaluate_goldens(rows)
    names = {g.name for g in fired}
    assert "contract_too_aggressive" in names
    # When only contract_too_aggressive fires, rebuild target is the
    # morning ritual prompt.
    assert choose_rebuild_target(fired) == "morning_ritual_prompt"


def test_wrong_diagnosis_three_consecutive_refusals():
    base = datetime(2026, 5, 5, 9, tzinfo=timezone.utc)
    rows = [
        _row(ts=base + timedelta(hours=i),
             distraction=20, predicted_distraction=20,
             op="propose_constructive_expression",
             diagnosis_need="fatigue",
             honored=False, violation_type="threshold_violation")
        for i in range(3)
    ]
    fired = evaluate_goldens(rows)
    assert any(g.name == "wrong_diagnosis_or_expression" for g in fired)


def test_choose_rebuild_target_priority_predictor_first():
    """When both predictor and catalog goldens fire, predictor wins."""
    pred_g = next(g for g in PERSONAL_GOLDEN_CASES if g.name == "morning_overconfidence")
    cat_g = next(g for g in PERSONAL_GOLDEN_CASES if g.name == "missing_need_in_catalog")
    assert choose_rebuild_target([pred_g, cat_g]) == "predictor"
    assert choose_rebuild_target([cat_g]) == "sublimation_catalog"
