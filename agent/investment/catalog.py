"""
The 6 named investment-failure-modes + their constructive expressions.

Maps directly to ``enhanced_investment_prd.md`` transformations 1-6
(collapsed to 6 substrate diagnoses):

| Failure mode             | PRD transformation                | Constructive expression |
|--------------------------|-----------------------------------|-------------------------|
| emotional                | #1: emotional → thesis-based      | File a PositionThesis  |
| narrative_following      | #2: narrative → mechanism         | Map causal mechanisms  |
| price_obsessed           | #3: price → signal extraction     | Pause; check thesis    |
| overconfident            | #4: overconfidence → calibration  | Log a CalibrationRecord|
| social_proof_following   | #5: social proof → independent    | Run BiasCheck via belief_os |
| ego_attached             | #6: ego → adaptive learning       | Write a kill-condition |
"""
from __future__ import annotations

from typing import Dict, List

from agent.domain_app.state import ConstructiveExpressionBase


_OPTIONS: Dict[str, List[ConstructiveExpressionBase]] = {
    "emotional": [
        ConstructiveExpressionBase(
            action="file_position_thesis_before_acting",
            duration_min=15,
            tank_credit_pct=4.0,
            references=["ontology.PositionThesis"],
        ),
        ConstructiveExpressionBase(
            action="defer_decision_24h",
            duration_min=1,
            tank_credit_pct=2.0,
            references=[],
        ),
    ],
    "narrative_following": [
        ConstructiveExpressionBase(
            action="map_causal_mechanism",
            duration_min=20,
            tank_credit_pct=3.0,
            references=["value_drivers", "bottlenecks", "dependencies"],
        ),
        ConstructiveExpressionBase(
            action="list_three_counter_narratives",
            duration_min=10,
            tank_credit_pct=2.0,
            references=[],
        ),
    ],
    "price_obsessed": [
        ConstructiveExpressionBase(
            action="pause_and_recheck_thesis",
            duration_min=10,
            tank_credit_pct=3.0,
            references=["ontology.PositionThesis"],
        ),
        ConstructiveExpressionBase(
            action="close_price_chart_for_24h",
            duration_min=1,
            tank_credit_pct=3.0,
            references=[],
        ),
    ],
    "overconfident": [
        ConstructiveExpressionBase(
            action="log_calibration_record",
            duration_min=5,
            tank_credit_pct=3.0,
            references=["ontology.CalibrationRecord"],
        ),
        ConstructiveExpressionBase(
            action="enumerate_three_failure_paths",
            duration_min=15,
            tank_credit_pct=3.0,
            references=[],
        ),
    ],
    "social_proof_following": [
        ConstructiveExpressionBase(
            action="run_belief_os_bias_check",
            duration_min=5,
            tank_credit_pct=4.0,
            references=["belief_os.check_decision_text", "ontology.BiasCheck"],
        ),
        ConstructiveExpressionBase(
            action="independently_evaluate_evidence_offline",
            duration_min=30,
            tank_credit_pct=3.0,
            references=[],
        ),
    ],
    "ego_attached": [
        ConstructiveExpressionBase(
            action="write_kill_condition_for_position",
            duration_min=10,
            tank_credit_pct=4.0,
            references=["ontology.PositionThesis.invalidation_condition"],
        ),
        ConstructiveExpressionBase(
            action="invert_role_play_a_short_seller",
            duration_min=15,
            tank_credit_pct=3.0,
            references=[],
        ),
    ],
}


class InvestmentCatalog:
    """Concrete ``DiagnosisCatalogProtocol`` for investment."""

    underlying_needs: List[str] = [
        "emotional",
        "narrative_following",
        "price_obsessed",
        "overconfident",
        "social_proof_following",
        "ego_attached",
    ]

    def options_for(self, need: str) -> List[ConstructiveExpressionBase]:
        return list(_OPTIONS.get(need, []))


INVESTMENT_CATALOG: InvestmentCatalog = InvestmentCatalog()
