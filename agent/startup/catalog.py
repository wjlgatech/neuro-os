"""
The 6 named startup-failure-modes + their constructive expressions.

Maps directly to ``enhanced_startup_prd.md`` transformations 1-6:

| Failure mode        | PRD transformation                  | Constructive expression |
|---------------------|-------------------------------------|-------------------------|
| idea_chaos          | #1: chaos → single-threaded         | Park idea; reaffirm thesis |
| broadcasting        | #2: broadcasting → signal listening | Capture AudienceSignal  |
| feature_creep       | #3: features → constraint discovery | Identify Bottleneck     |
| vision_intoxicated  | #4: vision → epistemic entrepreneur | Stress-test hypothesis  |
| vanity_metrics      | #5: vanity → trajectory metrics     | Switch to retention KPI |
| random_execution    | #6: random → tight OEC loops        | Run nightly OEC review  |
"""
from __future__ import annotations

from typing import Dict, List

from agent.domain_app.state import ConstructiveExpressionBase


_OPTIONS: Dict[str, List[ConstructiveExpressionBase]] = {
    "idea_chaos": [
        ConstructiveExpressionBase(
            action="park_idea_in_followups_queue",
            duration_min=2,
            tank_credit_pct=2.0,
            references=["ontology.StartupHypothesis"],
        ),
        ConstructiveExpressionBase(
            action="reaffirm_active_hypothesis_aloud",
            duration_min=5,
            tank_credit_pct=3.0,
            references=[],
        ),
    ],
    "broadcasting": [
        ConstructiveExpressionBase(
            action="capture_audience_signal_from_recent_interaction",
            duration_min=10,
            tank_credit_pct=4.0,
            references=["ontology.AudienceSignal"],
        ),
        ConstructiveExpressionBase(
            action="reply_thoughtfully_to_one_objection",
            duration_min=15,
            tank_credit_pct=3.0,
            references=[],
        ),
    ],
    "feature_creep": [
        ConstructiveExpressionBase(
            action="identify_current_bottleneck",
            duration_min=15,
            tank_credit_pct=4.0,
            references=["ontology.Bottleneck"],
        ),
        ConstructiveExpressionBase(
            action="answer_what_constraint_does_this_remove",
            duration_min=5,
            tank_credit_pct=2.0,
            references=[],
        ),
    ],
    "vision_intoxicated": [
        ConstructiveExpressionBase(
            action="stress_test_hypothesis_against_evidence",
            duration_min=20,
            tank_credit_pct=4.0,
            references=["ontology.StartupHypothesis.falsification_signal"],
        ),
        ConstructiveExpressionBase(
            action="enumerate_three_failure_paths",
            duration_min=15,
            tank_credit_pct=3.0,
            references=[],
        ),
    ],
    "vanity_metrics": [
        ConstructiveExpressionBase(
            action="switch_to_retention_or_repeat_engagement_kpi",
            duration_min=10,
            tank_credit_pct=3.0,
            references=["trust_density"],
        ),
        ConstructiveExpressionBase(
            action="delete_one_vanity_dashboard_widget",
            duration_min=5,
            tank_credit_pct=2.0,
            references=[],
        ),
    ],
    "random_execution": [
        ConstructiveExpressionBase(
            action="run_nightly_oec_review",
            duration_min=20,
            tank_credit_pct=4.0,
            references=["substrate.NightlySummary"],
        ),
        ConstructiveExpressionBase(
            action="write_tomorrow_one_priority_pre_commit",
            duration_min=5,
            tank_credit_pct=2.0,
            references=[],
        ),
    ],
}


class StartupCatalog:
    """Concrete ``DiagnosisCatalogProtocol`` for startup."""

    underlying_needs: List[str] = [
        "idea_chaos",
        "broadcasting",
        "feature_creep",
        "vision_intoxicated",
        "vanity_metrics",
        "random_execution",
    ]

    def options_for(self, need: str) -> List[ConstructiveExpressionBase]:
        return list(_OPTIONS.get(need, []))


STARTUP_CATALOG: StartupCatalog = StartupCatalog()
