"""
``agent.research`` — research vertical (one of three on the domain_app
substrate).

Audience: researchers who want to convert paper-collecting into
recursive world-model refinement.

Built per ``docs/prd/enhanced_research_prd.md`` with the Phase 0
sharpenings:

* 4 first-class metrics (not 10):
  - mechanism_extraction_rate (`MechanismCard count / paper bookmarks`)
  - assumption_extraction_rate (`assumptions extracted / paper`)
  - prediction_accuracy (`correct predictions / total predictions`)
  - thesis_continuity_score (`days on the load-bearing thesis`)
* 6 named failure modes (substrate-enforced):
  paper_collector, topic_hopper, memorizer, authority_acceptor,
  overloaded, forgetting.
* Iterations on a thesis are formally counted as ``MechanismCard``
  revisions OR ``PredictionLog`` entries citing the thesis.
* Privacy: notes default-private to research per
  ``cross_vertical.write_note`` default. Researchers explicitly opt
  into sharing mechanism cards with investment / startup.
"""
from __future__ import annotations

from agent.research.catalog import RESEARCH_CATALOG
from agent.research.ontology import (
    MechanismCard,
    PredictionLog,
    AssumptionMap,
    ResearchThesis,
    ResearchPriority,
    ResearchContract,
    EVIDENCE_TYPE,
    EXTRACTION_METHOD,
    RawSource,
    MechanismCardProposal,
    IngestionRun,
    GbrainEntity,
    GbrainQuerySpec,
)
from agent.research.config import ResearchConfig, make_research_app


__all__ = [
    "RESEARCH_CATALOG",
    "MechanismCard",
    "PredictionLog",
    "AssumptionMap",
    "ResearchThesis",
    "ResearchPriority",
    "ResearchContract",
    "EVIDENCE_TYPE",
    "EXTRACTION_METHOD",
    "RawSource",
    "MechanismCardProposal",
    "IngestionRun",
    "GbrainEntity",
    "GbrainQuerySpec",
    "ResearchConfig",
    "make_research_app",
]
