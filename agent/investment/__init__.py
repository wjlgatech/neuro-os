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
from agent.investment.config import (
    InvestmentConfig,
    make_investment_app,
    run_bias_check,
    run_cross_modal_bias_check,
)
from agent.investment.cost_of_living import (
    CostOfLivingTarget,
    make_cost_of_living_target,
    read_cost_of_living_target,
    write_cost_of_living_target,
)
from agent.investment.dashboard import (
    InvestDashboardSummary,
    build_invest_dashboard,
)
from agent.investment.dashboard import render_text as render_invest_dashboard
from agent.investment.ontology import (
    BiasCheck,
    CalibrationRecord,
    EVIDENCE_TYPE,
    InvestmentContract,
    InvestmentPriority,
    PositionThesis,
    Sleeve,
)
from agent.investment.trade import (
    TradeLog,
    TradeStrategy,
    iter_trade_logs,
    make_trade_log,
    write_trade_log,
)


__all__ = [
    "INVESTMENT_CATALOG",
    "InvestmentConfig",
    "make_investment_app",
    "run_bias_check",
    "run_cross_modal_bias_check",
    "BiasCheck",
    "CalibrationRecord",
    "EVIDENCE_TYPE",
    "InvestmentContract",
    "InvestmentPriority",
    "PositionThesis",
    "Sleeve",
    "CostOfLivingTarget",
    "make_cost_of_living_target",
    "read_cost_of_living_target",
    "write_cost_of_living_target",
    "TradeLog",
    "TradeStrategy",
    "iter_trade_logs",
    "make_trade_log",
    "write_trade_log",
    "InvestDashboardSummary",
    "build_invest_dashboard",
    "render_invest_dashboard",
]
