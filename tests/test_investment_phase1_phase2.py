"""
Tests for the Phase-1 / Phase-2 investment substrate:

  * options_income (Phase 1 — wheel / CSP / covered calls etc.)
  * megatrend (Phase 2 — sleeve balance + thesis-correct-rate)
  * cost_of_living (Phase 1 ↔ life — income gap + optional money-os bridge)
  * dashboard (rollup + system_health_flags)

These complement money-os (which has equity/ETF/crypto + cash-flow but
NO options + NO categorical mega-trend rollup).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agent.investment.cost_of_living import (
    CostOfLivingProfile,
    compute_income_gap,
    load_profile,
    read_from_money_os_profile,
    save_profile,
)
from agent.investment.dashboard import (
    PHASE1_INCOME_COVERAGE_THRESHOLD,
    build_dashboard_summary,
    render_text,
)
from agent.investment.megatrend import (
    OTHER_BUCKET,
    SLEEVE_CONCENTRATION_WARNING,
    compute_sleeve_balance,
    compute_thesis_correct_rate,
)
from agent.investment.ontology import PositionThesis
from agent.investment.options_income import (
    WINRATE_MIN_SAMPLE_SIZE,
    OptionTrade,
    compute_expected_value,
    compute_monthly_pnl,
    compute_winrate,
    list_open_trades,
    new_trade_id,
    read_trades,
    write_trade,
)


NOW = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Options income — EV math + winrate + monthly PNL
# ---------------------------------------------------------------------------


def test_expected_value_correct_signs_and_magnitudes():
    # 80% win-rate, $100 premium, $200 max-loss → EV = 0.8*100 - 0.2*200 = 40.
    assert compute_expected_value(
        win_probability=0.8, premium_received=100, max_loss=200,
    ) == pytest.approx(40.0)
    # 80% win-rate, $100 premium, $1000 max-loss → EV = 80 - 200 = -120.
    # The "high win rate but losing money" failure mode.
    assert compute_expected_value(
        win_probability=0.8, premium_received=100, max_loss=1000,
    ) == pytest.approx(-120.0)
    # 50/50, $100 vs $50 → EV = 50 - 25 = 25.
    assert compute_expected_value(
        win_probability=0.5, premium_received=100, max_loss=50,
    ) == pytest.approx(25.0)


def test_expected_value_rejects_out_of_range_probability():
    with pytest.raises(ValueError):
        compute_expected_value(win_probability=1.5, premium_received=100, max_loss=200)
    with pytest.raises(ValueError):
        compute_expected_value(win_probability=-0.1, premium_received=100, max_loss=200)


def _stub_trade(
    *, trade_id=None, strategy="cash_secured_put", ticker="AAPL",
    opened_at=NOW, outcome="open", realized_pnl=None, premium=100.0,
    max_loss=2000.0, parent_trade_id=None, closed_at=None,
):
    return OptionTrade(
        trade_id=trade_id or new_trade_id(),
        opened_at=opened_at,
        strategy=strategy,
        ticker=ticker,
        underlying_price_at_open=180.0,
        expiry="2026-06-19",
        strikes=[170.0],
        contracts=1,
        premium_received=premium,
        max_loss=max_loss,
        expected_value=compute_expected_value(
            win_probability=0.8, premium_received=premium, max_loss=max_loss,
        ),
        assignment_probability=0.2,
        outcome=outcome,
        closed_at=closed_at,
        realized_pnl=realized_pnl,
        parent_trade_id=parent_trade_id,
    )


def test_write_and_read_trades_round_trip(tmp_path):
    t1 = _stub_trade()
    t2 = _stub_trade(ticker="MSFT")
    write_trade(t1, home=tmp_path)
    write_trade(t2, home=tmp_path)
    trades = read_trades(home=tmp_path)
    assert len(trades) == 2
    assert {t.ticker for t in trades} == {"AAPL", "MSFT"}


def test_read_trades_filters_by_strategy_and_ticker(tmp_path):
    write_trade(_stub_trade(strategy="cash_secured_put", ticker="AAPL"), home=tmp_path)
    write_trade(_stub_trade(strategy="covered_call", ticker="AAPL"), home=tmp_path)
    write_trade(_stub_trade(strategy="cash_secured_put", ticker="MSFT"), home=tmp_path)
    assert len(read_trades(home=tmp_path, strategy="cash_secured_put")) == 2
    assert len(read_trades(home=tmp_path, ticker="AAPL")) == 2
    assert len(read_trades(
        home=tmp_path, strategy="cash_secured_put", ticker="AAPL",
    )) == 1


def test_compute_winrate_returns_noise_below_sample_threshold(tmp_path):
    for _ in range(5):
        write_trade(_stub_trade(outcome="won", realized_pnl=100.0,
                                closed_at=NOW), home=tmp_path)
    summary = compute_winrate(
        read_trades(home=tmp_path), strategy="cash_secured_put",
    )
    assert summary.closed_trades == 5
    assert summary.wins == 5
    assert summary.win_rate is None  # < WINRATE_MIN_SAMPLE_SIZE → noise


def test_compute_winrate_reports_rate_above_sample_threshold(tmp_path):
    for _ in range(WINRATE_MIN_SAMPLE_SIZE):
        write_trade(_stub_trade(outcome="won", realized_pnl=100.0, closed_at=NOW), home=tmp_path)
    for _ in range(5):
        write_trade(_stub_trade(outcome="lost", realized_pnl=-400.0, closed_at=NOW), home=tmp_path)
    summary = compute_winrate(
        read_trades(home=tmp_path), strategy="cash_secured_put",
    )
    assert summary.closed_trades == WINRATE_MIN_SAMPLE_SIZE + 5
    assert summary.wins == WINRATE_MIN_SAMPLE_SIZE
    assert summary.losses == 5
    assert summary.win_rate == pytest.approx(
        WINRATE_MIN_SAMPLE_SIZE / (WINRATE_MIN_SAMPLE_SIZE + 5)
    )
    # Realized PNL: 20 * 100 - 5 * 400 = 2000 - 2000 = 0. The "high win
    # rate but flat / losing money" failure mode.
    assert summary.realized_pnl_sum == pytest.approx(0.0)


def test_compute_monthly_pnl_buckets_by_closed_month(tmp_path):
    write_trade(_stub_trade(outcome="won", realized_pnl=200.0,
                            closed_at=datetime(2026, 5, 5, tzinfo=timezone.utc)),
                home=tmp_path)
    write_trade(_stub_trade(outcome="lost", realized_pnl=-150.0,
                            closed_at=datetime(2026, 5, 22, tzinfo=timezone.utc)),
                home=tmp_path)
    write_trade(_stub_trade(outcome="won", realized_pnl=100.0,
                            closed_at=datetime(2026, 6, 5, tzinfo=timezone.utc)),
                home=tmp_path)
    may = compute_monthly_pnl(read_trades(home=tmp_path), year_month="2026-05")
    jun = compute_monthly_pnl(read_trades(home=tmp_path), year_month="2026-06")
    assert may.closed_trades == 2 and may.realized_pnl == pytest.approx(50.0)
    assert jun.closed_trades == 1 and jun.realized_pnl == pytest.approx(100.0)


def test_list_open_trades_excludes_closed(tmp_path):
    open_t = _stub_trade(trade_id="parent")
    write_trade(open_t, home=tmp_path)
    open_only = list_open_trades(home=tmp_path)
    assert [t.trade_id for t in open_only] == ["parent"]
    # Now record a close.
    close_row = _stub_trade(
        trade_id="child", outcome="won", realized_pnl=100.0,
        closed_at=NOW, parent_trade_id="parent",
    )
    write_trade(close_row, home=tmp_path)
    assert list_open_trades(home=tmp_path) == []


# ---------------------------------------------------------------------------
# Mega-trend sleeve discipline
# ---------------------------------------------------------------------------


def _stub_thesis(
    *, id, sleeve=None, status="active", ts=None, instrument="NVDA",
):
    return PositionThesis(
        id=id,
        ts=ts or NOW,
        instrument=instrument,
        thesis="Thesis text long enough to clear the min_length gate.",
        evidence=["citation 1", "citation 2"],
        invalidation_condition="growth stalls below 5% YoY",
        expected_timeline="12-24 months",
        confidence="medium",
        sleeve=sleeve,
        status=status,
    )


def test_sleeve_balance_groups_by_sleeve_with_other_bucket():
    theses = [
        _stub_thesis(id="t1", sleeve="ai"),
        _stub_thesis(id="t2", sleeve="ai"),
        _stub_thesis(id="t3", sleeve="crypto"),
        _stub_thesis(id="t4", sleeve=None),  # → 'other'
    ]
    balance = compute_sleeve_balance(theses)
    sleeves = {a.sleeve for a in balance.allocations}
    assert sleeves == {"ai", "crypto", OTHER_BUCKET}
    ai = next(a for a in balance.allocations if a.sleeve == "ai")
    assert ai.thesis_count == 2
    assert ai.capital_fraction == pytest.approx(2 / 4)


def test_sleeve_balance_concentration_warning_fires_above_threshold():
    theses = [_stub_thesis(id=f"t{i}", sleeve="ai") for i in range(6)] + [
        _stub_thesis(id="t-other", sleeve="crypto"),
    ]
    # 6/7 = 85.7% in AI — well above the 40% threshold.
    balance = compute_sleeve_balance(theses)
    assert "ai" in balance.sleeves_concentrated
    ai = next(a for a in balance.allocations if a.sleeve == "ai")
    assert ai.over_concentration_warning is True
    assert ai.capital_fraction > SLEEVE_CONCENTRATION_WARNING


def test_sleeve_balance_respects_capital_weights():
    theses = [
        _stub_thesis(id="t1", sleeve="ai"),
        _stub_thesis(id="t2", sleeve="crypto"),
    ]
    # Weight crypto 5x larger — concentration should flip to crypto.
    balance = compute_sleeve_balance(
        theses, capital_weights={"t1": 1.0, "t2": 5.0},
    )
    crypto = next(a for a in balance.allocations if a.sleeve == "crypto")
    assert crypto.capital_fraction == pytest.approx(5.0 / 6.0)
    assert crypto.over_concentration_warning is True


def test_sleeve_balance_empty_input_safe():
    balance = compute_sleeve_balance([])
    assert balance.total_theses == 0
    assert balance.allocations == []


def test_thesis_correct_rate_counts_invalidations_in_window():
    inside = [
        _stub_thesis(id="active1", ts=NOW - timedelta(days=5), status="active"),
        _stub_thesis(id="active2", ts=NOW - timedelta(days=10), status="active"),
        _stub_thesis(id="killed", ts=NOW - timedelta(days=15), status="invalidated"),
    ]
    outside = [
        _stub_thesis(id="old_killed", ts=NOW - timedelta(days=60), status="invalidated"),
    ]
    r = compute_thesis_correct_rate(
        inside + outside, window_days=30, now=NOW,
    )
    assert r.total == 3
    assert r.invalidated == 1
    assert r.correct_rate == pytest.approx(2 / 3)


def test_thesis_correct_rate_empty_window_returns_none_rate():
    r = compute_thesis_correct_rate([], window_days=30, now=NOW)
    assert r.total == 0
    assert r.correct_rate is None


def test_thesis_correct_rate_sleeve_filter():
    theses = [
        _stub_thesis(id="ai1", ts=NOW, sleeve="ai", status="active"),
        _stub_thesis(id="ai2", ts=NOW, sleeve="ai", status="invalidated"),
        _stub_thesis(id="crypto1", ts=NOW, sleeve="crypto", status="active"),
    ]
    r = compute_thesis_correct_rate(theses, window_days=30, now=NOW, sleeve="ai")
    assert r.total == 2
    assert r.invalidated == 1
    assert r.correct_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Cost of living + income gap + money-os bridge
# ---------------------------------------------------------------------------


def test_save_and_load_profile_round_trip(tmp_path):
    p = CostOfLivingProfile(
        monthly_target=14000.0, region="Bay Area",
        breakdown="rent 5000, food 2000, ...", source="direct",
        written_at=NOW,
    )
    save_profile(p, home=tmp_path)
    got = load_profile(home=tmp_path)
    assert got is not None
    assert got.monthly_target == 14000.0
    assert got.source == "direct"


def test_load_profile_returns_none_when_missing(tmp_path):
    assert load_profile(home=tmp_path) is None


def test_compute_income_gap_uncovered_case():
    profile = CostOfLivingProfile(
        monthly_target=14000.0, source="direct", written_at=NOW,
    )
    gap = compute_income_gap(monthly_net_income=8000.0, profile=profile)
    assert gap.gap_dollars == pytest.approx(6000.0)
    assert gap.gap_pct == pytest.approx(6000 / 14000)


def test_compute_income_gap_surplus_case_runway_none():
    profile = CostOfLivingProfile(
        monthly_target=10000.0, source="direct", written_at=NOW,
    )
    gap = compute_income_gap(
        monthly_net_income=15000.0, profile=profile, savings_balance=100_000,
    )
    assert gap.gap_dollars < 0
    assert gap.months_runway_remaining is None  # no runway concept on surplus


def test_compute_income_gap_runway_computed_on_deficit():
    profile = CostOfLivingProfile(
        monthly_target=14000.0, source="direct", written_at=NOW,
    )
    gap = compute_income_gap(
        monthly_net_income=8000.0, profile=profile, savings_balance=60_000,
    )
    # 60k / 6k per month = 10 months.
    assert gap.months_runway_remaining == pytest.approx(10.0)


def test_read_from_money_os_profile_returns_none_when_missing(tmp_path):
    fake = tmp_path / "missing.md"
    assert read_from_money_os_profile(fake) is None


def test_read_from_money_os_profile_extracts_dollar_amount(tmp_path):
    md = tmp_path / "financial-identity.md"
    md.write_text(
        "# Financial identity\n\n"
        "Monthly expenses: $14,000 across rent + food + healthcare.\n",
        encoding="utf-8",
    )
    got = read_from_money_os_profile(md)
    assert got is not None
    assert got.monthly_target == pytest.approx(14000.0)
    assert got.source == "money_os_profile"


def test_read_from_money_os_profile_handles_k_suffix(tmp_path):
    md = tmp_path / "financial-identity.md"
    md.write_text("monthly_cost: $14k\n", encoding="utf-8")
    got = read_from_money_os_profile(md)
    assert got is not None
    assert got.monthly_target == pytest.approx(14000.0)


def test_read_from_money_os_profile_skips_unparseable(tmp_path):
    md = tmp_path / "financial-identity.md"
    md.write_text("Nothing about money here, just life context.\n", encoding="utf-8")
    assert read_from_money_os_profile(md) is None


# ---------------------------------------------------------------------------
# Dashboard rollup + health flags
# ---------------------------------------------------------------------------


def test_dashboard_empty_state_renders_with_health_flag(tmp_path):
    summary = build_dashboard_summary(theses=[], home=tmp_path, now=NOW)
    assert "no_cost_of_living_target" in summary.system_health_flags
    text = render_text(summary)
    assert "investment vertical" in text


def test_dashboard_income_gap_unmet_flag(tmp_path):
    # Profile says $14k/mo; close $5k of trades this month → gap 64%
    # → above the 30% threshold → flag fires.
    save_profile(
        CostOfLivingProfile(
            monthly_target=14000.0, source="direct", written_at=NOW,
        ),
        home=tmp_path,
    )
    closed_at = NOW
    write_trade(
        _stub_trade(outcome="won", realized_pnl=5000.0, closed_at=closed_at),
        home=tmp_path,
    )
    summary = build_dashboard_summary(theses=[], home=tmp_path, now=NOW)
    assert "phase1_income_gap_unmet" in summary.system_health_flags


def test_dashboard_no_concentration_when_balanced(tmp_path):
    save_profile(
        CostOfLivingProfile(monthly_target=10000.0, source="direct", written_at=NOW),
        home=tmp_path,
    )
    theses = [
        _stub_thesis(id="t1", sleeve="ai"),
        _stub_thesis(id="t2", sleeve="crypto"),
        _stub_thesis(id="t3", sleeve="space"),
    ]
    summary = build_dashboard_summary(theses=theses, home=tmp_path, now=NOW)
    assert "single_sleeve_concentration" not in summary.system_health_flags


def test_dashboard_concentration_flag(tmp_path):
    save_profile(
        CostOfLivingProfile(monthly_target=10000.0, source="direct", written_at=NOW),
        home=tmp_path,
    )
    # 5/6 in AI = 83% — far above 40%.
    theses = [_stub_thesis(id=f"t{i}", sleeve="ai") for i in range(5)] + [
        _stub_thesis(id="tx", sleeve="crypto"),
    ]
    summary = build_dashboard_summary(theses=theses, home=tmp_path, now=NOW)
    assert "single_sleeve_concentration" in summary.system_health_flags


def test_dashboard_no_thesis_invalidation_flag(tmp_path):
    save_profile(
        CostOfLivingProfile(monthly_target=10000.0, source="direct", written_at=NOW),
        home=tmp_path,
    )
    # ≥10 theses, all active = perfect foresight (suspicious).
    theses = [_stub_thesis(id=f"t{i}", sleeve="ai") for i in range(10)]
    summary = build_dashboard_summary(theses=theses, home=tmp_path, now=NOW, window_days=30)
    assert "no_thesis_invalidation" in summary.system_health_flags


def test_dashboard_options_loss_concentration_flag(tmp_path):
    save_profile(
        CostOfLivingProfile(monthly_target=10000.0, source="direct", written_at=NOW),
        home=tmp_path,
    )
    closed_at = NOW
    for _ in range(15):
        write_trade(
            _stub_trade(outcome="won", realized_pnl=100.0, closed_at=closed_at),
            home=tmp_path,
        )
    for _ in range(8):
        write_trade(
            _stub_trade(outcome="lost", realized_pnl=-400.0, closed_at=closed_at),
            home=tmp_path,
        )
    summary = build_dashboard_summary(theses=[], home=tmp_path, now=NOW, window_days=30)
    # 23 closed trades, sum = 1500 - 3200 = -1700 < 0 → flag fires.
    assert "options_loss_concentration" in summary.system_health_flags


def test_dashboard_renders_text_with_all_sections(tmp_path):
    save_profile(
        CostOfLivingProfile(monthly_target=14000.0, region="Bay Area",
                            source="direct", written_at=NOW),
        home=tmp_path,
    )
    write_trade(
        _stub_trade(outcome="won", realized_pnl=300.0, closed_at=NOW),
        home=tmp_path,
    )
    theses = [_stub_thesis(id="t1", sleeve="ai")]
    summary = build_dashboard_summary(theses=theses, home=tmp_path, now=NOW)
    text = render_text(summary)
    assert "Phase 1 — options income" in text
    assert "Phase 1 ↔ life" in text or "Phase 1 ↔ life" in text
    assert "Phase 2 — mega-trend sleeve" in text
    assert "Health flags" in text
    assert "Bay Area" not in text  # region isn't in render today; sanity that we don't false-positive


def test_phase1_threshold_constant_in_unit_range():
    assert 0.0 < PHASE1_INCOME_COVERAGE_THRESHOLD <= 1.0


def test_winrate_min_sample_size_is_sensible():
    assert WINRATE_MIN_SAMPLE_SIZE >= 10  # below 10 is meaningless
