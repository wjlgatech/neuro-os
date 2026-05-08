"""
The 6 named research-failure-modes + their constructive expressions.

Maps directly to ``enhanced_research_prd.md`` transformations 1–6,
which the PRD frames as Before/After pairs. We collapse them to 6
diagnoses (substrate-enforced count):

| Failure mode          | PRD transformation              | Constructive expression |
|-----------------------|---------------------------------|-------------------------|
| paper_collector       | #1: collecting → extracting     | Extract a MechanismCard |
| topic_hopper          | #2: hopping → continuity        | Bind reading to thesis  |
| memorizer             | #3: memorizing → predicting     | File a PredictionLog    |
| authority_acceptor    | #4: accepting → assumption-mapping | Build an AssumptionMap |
| overloaded            | #5: overload → high-signal      | Triage feed; cap at 1/d |
| forgetting            | #6: forgetting → ontology       | Open the thesis pane    |

All catalog entries here are immutable Pydantic instances — the
substrate's ``DiagnosisCatalogProtocol`` requires this so callers
can't accidentally swap an option's tank_credit.
"""
from __future__ import annotations

from typing import Dict, List

from agent.domain_app.state import ConstructiveExpressionBase


_OPTIONS: Dict[str, List[ConstructiveExpressionBase]] = {
    "paper_collector": [
        ConstructiveExpressionBase(
            action="extract_mechanism_card",
            duration_min=20,
            tank_credit_pct=4.0,
            references=["ontology.MechanismCard"],
        ),
        ConstructiveExpressionBase(
            action="delete_unprocessed_bookmarks",
            duration_min=10,
            tank_credit_pct=2.0,
            references=[],
        ),
    ],
    "topic_hopper": [
        ConstructiveExpressionBase(
            action="bind_reading_to_active_thesis",
            duration_min=5,
            tank_credit_pct=3.0,
            references=["ontology.ResearchThesis"],
        ),
        ConstructiveExpressionBase(
            action="park_idea_in_followups_queue",
            duration_min=2,
            tank_credit_pct=1.0,
            references=[],
        ),
    ],
    "memorizer": [
        ConstructiveExpressionBase(
            action="file_prediction_log",
            duration_min=10,
            tank_credit_pct=3.0,
            references=["ontology.PredictionLog"],
        ),
        ConstructiveExpressionBase(
            action="simulate_outcome_in_writing",
            duration_min=15,
            tank_credit_pct=3.0,
            references=[],
        ),
    ],
    "authority_acceptor": [
        ConstructiveExpressionBase(
            action="build_assumption_map",
            duration_min=15,
            tank_credit_pct=3.0,
            references=["ontology.AssumptionMap"],
        ),
        ConstructiveExpressionBase(
            action="list_invalidation_conditions",
            duration_min=10,
            tank_credit_pct=2.0,
            references=[],
        ),
    ],
    "overloaded": [
        ConstructiveExpressionBase(
            action="triage_feed_three_buckets",
            duration_min=10,
            tank_credit_pct=2.0,
            references=["hype/fluff/insight/mechanism"],
        ),
        ConstructiveExpressionBase(
            action="enforce_one_paper_per_day_cap",
            duration_min=2,
            tank_credit_pct=2.0,
            references=[],
        ),
    ],
    "forgetting": [
        ConstructiveExpressionBase(
            action="open_active_thesis_ontology",
            duration_min=5,
            tank_credit_pct=2.0,
            references=["ontology.ResearchThesis"],
        ),
        ConstructiveExpressionBase(
            action="re_paraphrase_three_random_cards",
            duration_min=10,
            tank_credit_pct=3.0,
            references=["mechanism_retention_score"],
        ),
    ],
}


class ResearchCatalog:
    """Concrete ``DiagnosisCatalogProtocol`` implementation for research.

    Class is intentionally a singleton-via-instance; tests can build
    their own catalog by extending this and overriding
    ``options_for``.
    """

    underlying_needs: List[str] = [
        "paper_collector",
        "topic_hopper",
        "memorizer",
        "authority_acceptor",
        "overloaded",
        "forgetting",
    ]

    def options_for(self, need: str) -> List[ConstructiveExpressionBase]:
        return list(_OPTIONS.get(need, []))


RESEARCH_CATALOG: ResearchCatalog = ResearchCatalog()
"""Module-level singleton other modules import."""
