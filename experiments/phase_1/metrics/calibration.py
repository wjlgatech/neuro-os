"""Calibration via Brier score on prediction-field success vs outcome.

For schema systems (B4/B5/Ours), each extracted card's `prediction` field
implies an expected probability of decision success. We use a fixed mapping
(card-quality → expected p) and compare to observed success rate.

For non-schema systems (B1/B2/B3), there's no prediction field to score, so
Brier is N/A; we report a sentinel value.
"""

from __future__ import annotations


# Expected success probability associated with each system's prediction field.
# A well-calibrated system's expected_p should match the observed success rate
# of decisions citing it.
EXPECTED_P_BY_SYSTEM = {
    "B4_single_shot_mechanism_card":  0.50,
    "B5_reviewed_mechanism_card":     0.60,
    "Ours_full_loop":                 0.75,
    # Wk 8 ablation systems — pre-registered before metrics computation.
    "Ours_v2_with_bias_check":        0.77,   # bias-check should slightly improve calibration
    "Ours_minus_review":              0.66,   # between B4 and B5 (skillify lift, no review)
}


def brier_score(system: str, decisions: list, outcomes: list) -> dict:
    """Compute Brier score and absolute calibration error for system."""
    expected_p = EXPECTED_P_BY_SYSTEM.get(system)
    if expected_p is None:
        return {
            "applicable": False,
            "reason": "system has no prediction field; calibration N/A",
        }

    outcome_by_id = {o.decision_id: o for o in outcomes}
    matched = [outcome_by_id[d.decision_id] for d in decisions if d.decision_id in outcome_by_id]
    if not matched:
        return {"applicable": True, "n": 0, "brier": None}

    observed_p = sum(1 for o in matched if o.success) / len(matched)
    brier = sum((expected_p - (1.0 if o.success else 0.0)) ** 2 for o in matched) / len(matched)
    abs_calib_error = abs(expected_p - observed_p)

    return {
        "applicable": True,
        "n": len(matched),
        "expected_p": expected_p,
        "observed_p": observed_p,
        "abs_calibration_error": abs_calib_error,
        "brier": brier,
    }
