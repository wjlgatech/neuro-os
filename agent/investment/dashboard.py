"""
Investment-vertical dashboard.

A pure-aggregation rollup over the three new substrate sources:

* ``option_trades.jsonl`` (Phase 1 income — wins / losses / monthly net)
* PositionThesis rows (Phase 2 — sleeve balance, thesis_correct_rate)
* CostOfLivingProfile (Phase 1 ↔ life — income gap)

NEVER writes. Reading the dashboard is idempotent.

Health flags fire only on unambiguous evidence (sample-size guards):

* ``phase1_income_gap_unmet`` — cost-of-living target set AND last
  month's options income < 70% of target.
* ``single_sleeve_concentration`` — any sleeve holds > 40% of capital
  across active theses.
* ``no_thesis_invalidation`` — ≥10 theses filed in window, zero
  invalidations. Either you have perfect foresight (unlikely) or
  you're not pulling the trigger on invalidations.
* ``options_loss_concentration`` — ≥20 closed trades, win-rate
  available, AND realized PNL is negative. The "high win rate but
  losing money" failure mode.
* ``no_cost_of_living_target`` — no CostOfLivingProfile set; the user
  is flying without the headline Phase-1 metric.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from agent.investment.cost_of_living import (
    IncomeGap,
    compute_income_gap,
    load_profile,
)
from agent.investment.megatrend import (
    SleeveBalance,
    ThesisCorrectRate,
    compute_sleeve_balance,
    compute_thesis_correct_rate,
)
from agent.investment.options_income import (
    MonthlyPnL,
    OptionStrategy,
    WinRateSummary,
    compute_monthly_pnl,
    compute_winrate,
    read_trades,
)
from agent.investment.ontology import PositionThesis


# Phase-1 income gap threshold — fires `phase1_income_gap_unmet` when
# last-month income covers less than this fraction of target. 0.70 is
# arbitrary; "you're more than 30% short" is a useful threshold.
PHASE1_INCOME_COVERAGE_THRESHOLD = 0.70


class InvestmentDashboardSummary(BaseModel):
    """Frozen one-shot rollup of the investment vertical."""

    model_config = ConfigDict(frozen=True)

    vertical: Literal["investment"] = "investment"
    window_days: int = Field(ge=1, le=365)
    generated_at: datetime

    # Phase 1 — options income.
    options_strategy_summaries: List[WinRateSummary] = Field(default_factory=list)
    options_monthly_pnl: Optional[MonthlyPnL] = None

    # Phase 1 ↔ life — cost of living.
    cost_of_living_target: Optional[float] = None
    income_gap: Optional[IncomeGap] = None

    # Phase 2 — mega-trend sleeve discipline.
    sleeve_balance: SleeveBalance = Field(default_factory=lambda: SleeveBalance(
        allocations=[], sleeves_concentrated=[], total_theses=0,
    ))
    thesis_correct_rate: Optional[ThesisCorrectRate] = None

    # Health flags.
    system_health_flags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Aggregation primitives
# ---------------------------------------------------------------------------


def _investment_home(home: Optional[Path]) -> Path:
    return home or (Path.home() / ".neuro_os_investment")


def _all_strategies() -> List[OptionStrategy]:
    return [
        "cash_secured_put",
        "covered_call",
        "wheel",
        "credit_spread",
        "iron_condor",
        "naked",
        "other",
    ]


def _compute_health_flags(
    *,
    summary_in_progress: dict,
    profile_exists: bool,
) -> List[str]:
    flags: List[str] = []
    if not profile_exists:
        flags.append("no_cost_of_living_target")

    gap = summary_in_progress.get("income_gap")
    if gap is not None and gap.gap_pct > (1.0 - PHASE1_INCOME_COVERAGE_THRESHOLD):
        flags.append("phase1_income_gap_unmet")

    balance: SleeveBalance = summary_in_progress["sleeve_balance"]
    if balance.sleeves_concentrated:
        flags.append("single_sleeve_concentration")

    rate: Optional[ThesisCorrectRate] = summary_in_progress.get("thesis_correct_rate")
    if rate is not None and rate.total >= 10 and rate.invalidated == 0:
        flags.append("no_thesis_invalidation")

    # options_loss_concentration: a strategy with ≥20 closed trades and
    # realized_pnl_sum negative is the "high win rate, losing money"
    # failure pattern.
    for s in summary_in_progress["options_strategy_summaries"]:
        if s.closed_trades >= 20 and s.realized_pnl_sum < 0.0:
            flags.append("options_loss_concentration")
            break

    return flags


def build_dashboard_summary(
    *,
    theses: Optional[List[PositionThesis]] = None,
    home: Optional[Path] = None,
    window_days: int = 30,
    now: Optional[datetime] = None,
) -> InvestmentDashboardSummary:
    """Build the rollup. Reads only; writes nothing.

    ``theses`` is passed in because PositionThesis rows have no shared
    on-disk format yet (the investment vertical's config.write_* and
    read_* helpers handle that). Callers typically pass the result of
    ``list_position_theses(home)`` or equivalent.
    """
    when = now or datetime.now(timezone.utc)
    cutoff = when - timedelta(days=window_days)

    # Options income.
    all_trades = read_trades(home=home, since=cutoff)
    summaries: List[WinRateSummary] = []
    for strategy in _all_strategies():
        s = compute_winrate(all_trades, strategy=strategy)
        if s.closed_trades > 0:
            summaries.append(s)
    last_month_str = (when - timedelta(days=30)).strftime("%Y-%m")
    this_month_str = when.strftime("%Y-%m")
    monthly = compute_monthly_pnl(all_trades, year_month=this_month_str)
    # If this_month has zero closed trades but last_month has data, use last_month.
    if monthly.closed_trades == 0 and monthly.realized_pnl == 0.0:
        last_monthly = compute_monthly_pnl(all_trades, year_month=last_month_str)
        if last_monthly.closed_trades > 0 or last_monthly.realized_pnl != 0.0:
            monthly = last_monthly

    # Cost of living + income gap.
    profile = load_profile(home=home)
    income_gap: Optional[IncomeGap] = None
    if profile is not None:
        income_gap = compute_income_gap(
            monthly_net_income=monthly.realized_pnl,
            profile=profile,
        )

    # Mega-trend sleeve discipline.
    theses_input = theses or []
    balance = compute_sleeve_balance(theses_input)
    rate = compute_thesis_correct_rate(theses_input, window_days=window_days, now=when)

    in_progress = {
        "options_strategy_summaries": summaries,
        "options_monthly_pnl": monthly,
        "income_gap": income_gap,
        "sleeve_balance": balance,
        "thesis_correct_rate": rate,
    }
    flags = _compute_health_flags(
        summary_in_progress=in_progress,
        profile_exists=profile is not None,
    )

    return InvestmentDashboardSummary(
        window_days=window_days,
        generated_at=when,
        options_strategy_summaries=summaries,
        options_monthly_pnl=monthly,
        cost_of_living_target=profile.monthly_target if profile else None,
        income_gap=income_gap,
        sleeve_balance=balance,
        thesis_correct_rate=rate,
        system_health_flags=flags,
    )


# ---------------------------------------------------------------------------
# Text renderer
# ---------------------------------------------------------------------------


def render_text(summary: InvestmentDashboardSummary) -> str:
    """Render the rollup as ~25 lines of plain text."""
    lines: List[str] = []
    when = summary.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    lines.append(
        f"investment vertical — {summary.window_days}-day dashboard (generated {when})"
    )
    lines.append("=" * 70)
    lines.append("")

    lines.append("Phase 1 — options income")
    if summary.options_monthly_pnl:
        m = summary.options_monthly_pnl
        lines.append(
            f"  month {m.year_month}: realized={m.realized_pnl:>10,.0f}"
            f"   closed_trades={m.closed_trades}"
            f"   opened_premium={m.premium_received_open:,.0f}"
        )
    else:
        lines.append("  (no closed trades)")
    if summary.options_strategy_summaries:
        for s in summary.options_strategy_summaries:
            wr = (
                f"{s.win_rate * 100:.0f}%"
                if s.win_rate is not None
                else "noise (<20 trades)"
            )
            lines.append(
                f"  {s.strategy:24s} closed={s.closed_trades:>3d}"
                f"  wr={wr:>16s}  pnl={s.realized_pnl_sum:>10,.0f}"
            )
    else:
        lines.append("  (no strategy data yet)")
    lines.append("")

    lines.append("Phase 1 ↔ life — income gap")
    if summary.cost_of_living_target is not None and summary.income_gap:
        g = summary.income_gap
        sign = "uncovered" if g.gap_dollars > 0 else "surplus"
        lines.append(
            f"  target={g.target:>10,.0f}/mo"
            f"   net_income={g.monthly_net_income:>10,.0f}"
            f"   gap={g.gap_dollars:>10,.0f}  ({g.gap_pct*100:.0f}% {sign})"
        )
        if g.months_runway_remaining is not None:
            lines.append(f"  runway: {g.months_runway_remaining:.1f} months at this gap rate.")
    else:
        lines.append("  (no cost-of-living target set)")
    lines.append("")

    lines.append("Phase 2 — mega-trend sleeve discipline")
    if summary.sleeve_balance.allocations:
        for a in summary.sleeve_balance.allocations:
            warn = " *over-concentrated*" if a.over_concentration_warning else ""
            lines.append(
                f"  {a.sleeve:16s} theses={a.thesis_count:>3d}"
                f"   capital={a.capital_fraction*100:>5.1f}%{warn}"
            )
    else:
        lines.append("  (no theses)")
    if summary.thesis_correct_rate and summary.thesis_correct_rate.total > 0:
        r = summary.thesis_correct_rate
        pct = f"{r.correct_rate*100:.0f}%" if r.correct_rate is not None else "—"
        lines.append(
            f"  thesis-correct-rate over {r.window_days}d: {pct}"
            f"  ({r.total - r.invalidated}/{r.total} not invalidated)"
        )
    lines.append("")

    lines.append("Health flags")
    if summary.system_health_flags:
        lines.append(f"  {', '.join(summary.system_health_flags)}")
    else:
        lines.append("  (none)")
    lines.append("")

    return "\n".join(lines)


__all__ = [
    "PHASE1_INCOME_COVERAGE_THRESHOLD",
    "InvestmentDashboardSummary",
    "build_dashboard_summary",
    "render_text",
]
