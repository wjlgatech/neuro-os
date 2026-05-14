"""H1 — Mechanism survival rate (primary).

Defined as: fraction of extracted cards that are CITED in at least one
downstream decision within the 40-day window AND whose cited aspect produces
a SUCCESS outcome.

Schema-less systems (B1/B2/B3) have no field-level citations; their decisions
cite the free-text output as a whole, so we count survival as
"decisions citing this paper's output succeeded." Schema systems get
field-level citations.
"""

from __future__ import annotations

from collections import defaultdict


def survival_rate(extractions: list, decisions: list, outcomes: list) -> dict:
    """Return per-system survival statistics."""
    # Index outcomes by decision_id for O(1) lookup.
    outcome_by_id = {o.decision_id: o for o in outcomes}

    # Group decisions by cited_paper_id.
    decisions_by_paper: dict[str, list] = defaultdict(list)
    for d in decisions:
        decisions_by_paper[d.cited_paper_id].append(d)

    # For each extraction, count its surviving citations.
    surviving_cards = 0
    total_cards = 0
    total_successful_citations = 0
    total_citations = 0

    for e in extractions:
        total_cards += 1
        cites = decisions_by_paper.get(e.paper_id, [])
        success_count = 0
        for d in cites:
            o = outcome_by_id.get(d.decision_id)
            if o is None:
                continue
            total_citations += 1
            if o.success:
                total_successful_citations += 1
                success_count += 1
        if success_count >= 1:
            surviving_cards += 1

    return {
        "survival_rate_cards": surviving_cards / total_cards if total_cards else 0.0,
        "survival_rate_citations": (
            total_successful_citations / total_citations if total_citations else 0.0
        ),
        "surviving_cards": surviving_cards,
        "total_cards": total_cards,
        "successful_citations": total_successful_citations,
        "total_citations": total_citations,
    }
