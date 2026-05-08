"""
``agent.investment`` — investment vertical (advisory-only v0).

⚠️ **CRITICAL ANTI-GOAL**: this vertical is ADVISORY-ONLY. It does NOT
execute trades, integrate with brokers, or move money. It logs theses,
scores them, surfaces bias warnings, and produces nightly summaries.
The user reads the output and makes their own decisions. (This was
locked as a Phase 0 PRD revision; v1 may add broker integration with
explicit user consent + a dedicated kill-switch.)

Built per ``docs/prd/enhanced_investment_prd.md`` with the Phase 0
sharpenings:

* 4 first-class metrics: calibration error, thesis survival rate,
  bias detection rate, decision consistency.
* 6 named failure modes:
  emotional, narrative_following, price_obsessed, overconfident,
  social_proof_following, ego_attached.
* Reuses ``agent/belief_os.py::check_decision_text`` for bias
  detection. Does NOT re-implement bias logic.
* Reuses the existing ``Confidence = Literal["low", "medium", "high"]``
  enum. Does NOT introduce a parallel 0-1 float scale.
* Privacy: notes default-PRIVATE to investment per cross_vertical
  default. Theses with positions/sizing stay local; researchers and
  founders can't read them unless investor explicitly opts in.
"""
from __future__ import annotations

from agent.investment.catalog import INVESTMENT_CATALOG
from agent.investment.config import InvestmentConfig, make_investment_app
from agent.investment.ontology import (
    BiasCheck,
    CalibrationRecord,
    EVIDENCE_TYPE,
    InvestmentContract,
    InvestmentPriority,
    PositionThesis,
)


__all__ = [
    "INVESTMENT_CATALOG",
    "InvestmentConfig",
    "make_investment_app",
    "BiasCheck",
    "CalibrationRecord",
    "EVIDENCE_TYPE",
    "InvestmentContract",
    "InvestmentPriority",
    "PositionThesis",
]
