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
    CostOfLivingProfile,
    IncomeGap,
    compute_income_gap,
    load_profile,
    read_from_money_os_profile,
    save_profile,
)
from agent.investment.dashboard import (
    PHASE1_INCOME_COVERAGE_THRESHOLD,
    InvestmentDashboardSummary,
    build_dashboard_summary,
    render_text as render_dashboard_text,
)
from agent.investment.megatrend import (
    OTHER_BUCKET,
    SLEEVE_CONCENTRATION_WARNING,
    SleeveAllocation,
    SleeveBalance,
    ThesisCorrectRate,
    compute_sleeve_balance,
    compute_thesis_correct_rate,
)
from agent.investment.ontology import (
    BiasCheck,
    CalibrationRecord,
    EVIDENCE_TYPE,
    InvestmentContract,
    InvestmentPriority,
    MegaTrendSleeve,
    PositionThesis,
)
from agent.investment.options_income import (
    WINRATE_MIN_SAMPLE_SIZE,
    MonthlyPnL,
    OptionOutcome,
    OptionStrategy,
    OptionTrade,
    WinRateSummary,
    compute_expected_value,
    compute_monthly_pnl,
    compute_winrate,
    list_open_trades,
    new_trade_id,
    option_trades_path,
    read_trades,
    write_trade,
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
    "MegaTrendSleeve",
    # Phase 1: options income
    "OptionStrategy",
    "OptionOutcome",
    "OptionTrade",
    "WINRATE_MIN_SAMPLE_SIZE",
    "WinRateSummary",
    "MonthlyPnL",
    "option_trades_path",
    "write_trade",
    "read_trades",
    "compute_expected_value",
    "compute_winrate",
    "compute_monthly_pnl",
    "list_open_trades",
    "new_trade_id",
    # Phase 1 ↔ life: cost of living
    "CostOfLivingProfile",
    "IncomeGap",
    "save_profile",
    "load_profile",
    "read_from_money_os_profile",
    "compute_income_gap",
    # Phase 2: mega-trend sleeve discipline
    "SLEEVE_CONCENTRATION_WARNING",
    "OTHER_BUCKET",
    "SleeveAllocation",
    "SleeveBalance",
    "ThesisCorrectRate",
    "compute_sleeve_balance",
    "compute_thesis_correct_rate",
    # Dashboard
    "PHASE1_INCOME_COVERAGE_THRESHOLD",
    "InvestmentDashboardSummary",
    "build_dashboard_summary",
    "render_dashboard_text",
]
