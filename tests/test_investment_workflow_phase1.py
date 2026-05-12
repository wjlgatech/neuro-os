"""
Phase-1 invest workflow tests.

Covers:
* ``PositionThesis.sleeve`` (new field)
* ``CostOfLivingTarget`` schema + read/write helpers
* ``TradeLog`` schema + read/write/iter helpers
* (Dashboard + CLI tests live in their own files; see plan doc.)

Advisory-only invariant: TradeLog must NOT introduce execution-shaped
evidence types into ``EVIDENCE_TYPE``. Pinned.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from agent.investment import (
    EVIDENCE_TYPE,
    CostOfLivingTarget,
    PositionThesis,
    TradeStrategy,
    iter_trade_logs,
    make_cost_of_living_target,
    make_trade_log,
    read_cost_of_living_target,
    write_cost_of_living_target,
    write_trade_log,
)


# ---------------------------------------------------------------------------
# PositionThesis.sleeve
# ---------------------------------------------------------------------------


def _base_thesis_kwargs():
    return dict(
        id="t1",
        ts=datetime.now(timezone.utc),
        instrument="NVDA",
        thesis="AI inference compute demand outstrips fab capacity through 2027.",
        evidence=["hyperscaler capex guidance", "CoWoS capacity constraints"],
        invalidation_condition="hyperscaler capex guides flat for 2 consecutive quarters",
        expected_timeline="18 months",
        confidence="medium",
    )


def test_position_thesis_accepts_sleeve_field():
    thesis = PositionThesis(**_base_thesis_kwargs(), sleeve="ai")
    assert thesis.sleeve == "ai"


def test_position_thesis_sleeve_defaults_to_none():
    thesis = PositionThesis(**_base_thesis_kwargs())
    assert thesis.sleeve is None


def test_position_thesis_rejects_unknown_sleeve():
    with pytest.raises(ValidationError):
        PositionThesis(**_base_thesis_kwargs(), sleeve="quantum_computing")


def test_position_thesis_accepts_every_named_sleeve():
    for sleeve in ("ai", "energy", "biotech", "macro", "crypto", "other"):
        thesis = PositionThesis(**_base_thesis_kwargs(), sleeve=sleeve)
        assert thesis.sleeve == sleeve


# ---------------------------------------------------------------------------
# CostOfLivingTarget
# ---------------------------------------------------------------------------


def test_cost_of_living_target_validates_positive_target():
    with pytest.raises(ValidationError):
        CostOfLivingTarget(
            monthly_target=0.0,
            region="Bay Area",
            ts=datetime.now(timezone.utc),
        )
    with pytest.raises(ValidationError):
        CostOfLivingTarget(
            monthly_target=-500.0,
            region="Bay Area",
            ts=datetime.now(timezone.utc),
        )


def test_cost_of_living_target_rejects_absurd_upper_bound():
    with pytest.raises(ValidationError):
        CostOfLivingTarget(
            monthly_target=2_000_000.0,
            region="Bay Area",
            ts=datetime.now(timezone.utc),
        )


def test_cost_of_living_set_writes_and_reads_back(tmp_path):
    target = make_cost_of_living_target(
        monthly_target=14000.0,
        region="Bay Area",
        notes="post-rent baseline",
    )
    path = write_cost_of_living_target(target, home=tmp_path)
    assert path.exists()
    assert path.name == "cost_of_living.json"

    loaded = read_cost_of_living_target(home=tmp_path)
    assert loaded is not None
    assert loaded.monthly_target == 14000.0
    assert loaded.region == "Bay Area"
    assert loaded.notes == "post-rent baseline"


def test_cost_of_living_set_overwrites_existing(tmp_path):
    write_cost_of_living_target(
        make_cost_of_living_target(monthly_target=10000.0, region="Austin"),
        home=tmp_path,
    )
    write_cost_of_living_target(
        make_cost_of_living_target(monthly_target=14000.0, region="Bay Area"),
        home=tmp_path,
    )
    loaded = read_cost_of_living_target(home=tmp_path)
    assert loaded is not None
    assert loaded.monthly_target == 14000.0
    assert loaded.region == "Bay Area"


def test_cost_of_living_read_returns_none_when_missing(tmp_path):
    assert read_cost_of_living_target(home=tmp_path) is None


def test_cost_of_living_target_is_frozen():
    target = make_cost_of_living_target(monthly_target=10000.0, region="X")
    with pytest.raises(ValidationError):
        target.monthly_target = 20000.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TradeLog
# ---------------------------------------------------------------------------


def _csp_kwargs(**overrides):
    base = dict(
        strategy="cash_secured_put",
        ticker="NVDA",
        underlying_price=920.0,
        expiry=date(2026, 6, 19),
        strikes=[880.0],
        premium=1200.0,
        max_loss=88000.0,
        win_prob=0.80,
        assignment_prob=0.20,
    )
    base.update(overrides)
    return base


def test_trade_log_strategy_enum_contains_cash_secured_put():
    valid: set[str] = set(TradeStrategy.__args__)  # type: ignore[attr-defined]
    assert "cash_secured_put" in valid
    assert "covered_call" in valid
    assert "iron_condor" in valid
    assert "other" in valid


def test_trade_log_strategy_enum_has_no_execution_shaped_terms():
    """Advisory-only guard: the trade strategy enum must not contain
    broker-only operations like 'market_order' or 'sweep_order' that
    would imply execution routing."""
    valid: set[str] = set(TradeStrategy.__args__)  # type: ignore[attr-defined]
    for forbidden in (
        "market_order", "limit_order", "stop_order", "sweep_order",
        "route_to_broker", "execute",
    ):
        assert forbidden not in valid


def test_trade_log_validates_win_prob_range():
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(win_prob=1.5))
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(win_prob=-0.1))


def test_trade_log_validates_assignment_prob_range():
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(assignment_prob=1.5))
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(assignment_prob=-0.1))


def test_trade_log_requires_at_least_one_strike():
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(strikes=[]))


def test_trade_log_rejects_more_than_four_strikes():
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(strikes=[1.0, 2.0, 3.0, 4.0, 5.0]))


def test_trade_log_requires_positive_premium():
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(premium=0.0))
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(premium=-100.0))


def test_trade_log_requires_positive_max_loss():
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(max_loss=0.0))


def test_trade_log_requires_positive_underlying_price():
    with pytest.raises(ValidationError):
        make_trade_log(**_csp_kwargs(underlying_price=0.0))


def test_trade_log_is_frozen():
    trade = make_trade_log(**_csp_kwargs())
    with pytest.raises(ValidationError):
        trade.premium = 9999.0  # type: ignore[misc]


def test_trade_log_writes_to_trades_dir(tmp_path):
    trade = make_trade_log(**_csp_kwargs())
    path = write_trade_log(trade, home=tmp_path)
    assert path.exists()
    assert path.parent.name == "trades"
    assert path.name == f"{trade.id}.json"


def test_trade_log_round_trip(tmp_path):
    original = make_trade_log(**_csp_kwargs(notes="thursday morning"))
    write_trade_log(original, home=tmp_path)

    loaded = list(iter_trade_logs(home=tmp_path))
    assert len(loaded) == 1
    reloaded = loaded[0]
    assert reloaded.id == original.id
    assert reloaded.strategy == "cash_secured_put"
    assert reloaded.ticker == "NVDA"
    assert reloaded.strikes == [880.0]
    assert reloaded.premium == 1200.0
    assert reloaded.notes == "thursday morning"


def test_iter_trade_logs_empty_when_dir_missing(tmp_path):
    """A vertical home with no trades/ subdir must yield nothing,
    not crash. The dashboard relies on this for the empty-state path."""
    assert list(iter_trade_logs(home=tmp_path)) == []


def test_iter_trade_logs_skips_malformed_files(tmp_path):
    """Corrupted JSON files in trades/ are skipped, not raised. The
    dashboard's audit surface must not crash on a single bad row."""
    good = make_trade_log(**_csp_kwargs())
    write_trade_log(good, home=tmp_path)
    bad_path = (tmp_path / "trades" / "bad.json")
    bad_path.write_text("{not valid json", encoding="utf-8")

    loaded = list(iter_trade_logs(home=tmp_path))
    assert len(loaded) == 1
    assert loaded[0].id == good.id


def test_iter_trade_logs_filters_by_window_days(tmp_path):
    now = datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)
    recent = make_trade_log(
        **_csp_kwargs(),
        ts=now - timedelta(days=5),
    )
    old = make_trade_log(
        **_csp_kwargs(),
        ts=now - timedelta(days=45),
    )
    write_trade_log(recent, home=tmp_path)
    write_trade_log(old, home=tmp_path)

    in_window = list(iter_trade_logs(home=tmp_path, window_days=30, now=now))
    assert len(in_window) == 1
    assert in_window[0].id == recent.id


def test_trade_log_supports_sleeve_field(tmp_path):
    trade = make_trade_log(**_csp_kwargs(sleeve="ai"))
    assert trade.sleeve == "ai"
    write_trade_log(trade, home=tmp_path)
    [reloaded] = list(iter_trade_logs(home=tmp_path))
    assert reloaded.sleeve == "ai"


def test_trade_log_sleeve_defaults_to_none():
    trade = make_trade_log(**_csp_kwargs())
    assert trade.sleeve is None


# ---------------------------------------------------------------------------
# Advisory-only invariant (cross-module)
# ---------------------------------------------------------------------------


def test_evidence_type_enum_still_has_no_execution_terms():
    """Adding TradeLog must NOT broaden EVIDENCE_TYPE with execution-shaped
    entries. The invariant from test_investment_vertical is reaffirmed here
    so the workflow surface is bound by it too."""
    valid: set[str] = set(EVIDENCE_TYPE.__args__)  # type: ignore[attr-defined]
    for forbidden in (
        "trade_executed", "order_filled", "order_routed",
        "position_opened", "position_closed",
    ):
        assert forbidden not in valid


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


from agent.investment import (  # noqa: E402  (grouping by feature)
    InvestDashboardSummary,
    build_invest_dashboard,
    render_invest_dashboard,
)
from agent.investment.config import write_position_thesis  # noqa: E402


_NOW = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)


def test_dashboard_empty_state_returns_valid_summary(tmp_path):
    summary = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    assert isinstance(summary, InvestDashboardSummary)
    assert summary.vertical == "investment"
    assert summary.window_days == 30
    assert summary.monthly_target is None
    assert summary.region is None
    assert summary.premium_collected_in_window == 0.0
    assert summary.premium_per_month_run_rate == 0.0
    assert summary.cost_of_living_coverage_pct is None
    assert summary.trades_in_window == 0
    assert summary.trades_by_strategy == {}
    assert summary.max_loss_exposure_total == 0.0
    assert summary.mean_win_prob is None
    assert summary.mean_assignment_prob is None
    assert summary.theses_by_sleeve == {}
    assert summary.calibration_error_in_window is None
    assert summary.bias_checks_in_window == 0


def test_dashboard_aggregates_trades_in_window(tmp_path):
    write_trade_log(
        make_trade_log(**_csp_kwargs(), ts=_NOW - timedelta(days=5)),
        home=tmp_path,
    )
    write_trade_log(
        make_trade_log(
            **_csp_kwargs(strategy="covered_call", premium=500.0, max_loss=20000.0),
            ts=_NOW - timedelta(days=10),
        ),
        home=tmp_path,
    )
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    assert s.trades_in_window == 2
    assert s.premium_collected_in_window == 1700.0
    assert s.max_loss_exposure_total == 108000.0
    assert s.trades_by_strategy == {"cash_secured_put": 1, "covered_call": 1}
    assert s.mean_win_prob == pytest.approx(0.80)
    assert s.mean_assignment_prob == pytest.approx(0.20)


def test_dashboard_excludes_trades_outside_window(tmp_path):
    write_trade_log(
        make_trade_log(**_csp_kwargs(), ts=_NOW - timedelta(days=5)),
        home=tmp_path,
    )
    write_trade_log(
        make_trade_log(**_csp_kwargs(), ts=_NOW - timedelta(days=45)),
        home=tmp_path,
    )
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    assert s.trades_in_window == 1
    assert s.premium_collected_in_window == 1200.0


def test_dashboard_cost_of_living_run_rate(tmp_path):
    """run-rate = premium_window × 30 / window_days. 30-day window with
    $3000 premium → $3000/mo; 60-day window with $3000 → $1500/mo."""
    write_cost_of_living_target(
        make_cost_of_living_target(monthly_target=14000.0, region="Bay Area"),
        home=tmp_path,
    )
    for _ in range(3):
        write_trade_log(
            make_trade_log(**_csp_kwargs(premium=1000.0), ts=_NOW - timedelta(days=5)),
            home=tmp_path,
        )
    s30 = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    assert s30.premium_collected_in_window == 3000.0
    assert s30.premium_per_month_run_rate == pytest.approx(3000.0)

    s60 = build_invest_dashboard(home=tmp_path, window_days=60, now=_NOW)
    assert s60.premium_per_month_run_rate == pytest.approx(1500.0)


def test_dashboard_coverage_pct_with_target(tmp_path):
    write_cost_of_living_target(
        make_cost_of_living_target(monthly_target=10000.0, region="X"),
        home=tmp_path,
    )
    write_trade_log(
        make_trade_log(**_csp_kwargs(premium=5000.0), ts=_NOW - timedelta(days=5)),
        home=tmp_path,
    )
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    # premium $5000 over 30 days → $5000/mo run-rate → 50% of $10k target.
    assert s.cost_of_living_coverage_pct == pytest.approx(0.5)


def test_dashboard_coverage_pct_is_none_without_target(tmp_path):
    write_trade_log(
        make_trade_log(**_csp_kwargs(), ts=_NOW - timedelta(days=5)),
        home=tmp_path,
    )
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    assert s.cost_of_living_coverage_pct is None
    assert s.monthly_target is None
    assert s.region is None


def test_dashboard_sleeve_allocation(tmp_path):
    write_position_thesis(
        thesis=PositionThesis(**_base_thesis_kwargs(), sleeve="ai"),
        home=tmp_path,
    )
    write_position_thesis(
        thesis=PositionThesis(
            **{**_base_thesis_kwargs(), "id": "t2"},
            sleeve="ai",
        ),
        home=tmp_path,
    )
    write_position_thesis(
        thesis=PositionThesis(
            **{**_base_thesis_kwargs(), "id": "t3"},
            sleeve="energy",
        ),
        home=tmp_path,
    )
    # An untagged thesis (no sleeve)
    write_position_thesis(
        thesis=PositionThesis(**{**_base_thesis_kwargs(), "id": "t4"}),
        home=tmp_path,
    )
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    assert s.theses_by_sleeve == {"ai": 2, "energy": 1, "untagged": 1}


def test_dashboard_sleeve_skips_invalidated_theses(tmp_path):
    """Only ACTIVE theses count in the allocation view. Invalidated
    rows are journal entries, not current exposure."""
    write_position_thesis(
        thesis=PositionThesis(**_base_thesis_kwargs(), sleeve="ai"),
        home=tmp_path,
    )
    write_position_thesis(
        thesis=PositionThesis(
            **{**_base_thesis_kwargs(), "id": "t2", "status": "invalidated"},
            sleeve="ai",
        ),
        home=tmp_path,
    )
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    assert s.theses_by_sleeve == {"ai": 1}


def test_dashboard_calibration_error_in_window(tmp_path):
    """Mirrors the nightly() calibration calc, but windowed."""
    import json as _json

    cal_dir = tmp_path / "calibration_records"
    cal_dir.mkdir(parents=True, exist_ok=True)
    # In-window record: predicted high (0.85), actual valid (1.0) → err 0.15
    (cal_dir / "r1.json").write_text(_json.dumps({
        "id": "r1",
        "ts": (_NOW - timedelta(days=5)).isoformat(),
        "thesis_id": "t1",
        "predicted_confidence": "high",
        "thesis_still_valid": True,
    }))
    # Out-of-window record (ignored)
    (cal_dir / "r2.json").write_text(_json.dumps({
        "id": "r2",
        "ts": (_NOW - timedelta(days=100)).isoformat(),
        "thesis_id": "t2",
        "predicted_confidence": "low",
        "thesis_still_valid": False,
    }))
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    assert s.calibration_error_in_window == pytest.approx(0.15)


def test_dashboard_counts_bias_checks_in_window(tmp_path):
    import json as _json

    bias_dir = tmp_path / "bias_checks"
    bias_dir.mkdir(parents=True, exist_ok=True)
    (bias_dir / "b1.json").write_text(_json.dumps({
        "id": "b1",
        "ts": (_NOW - timedelta(days=2)).isoformat(),
        "thesis_id": "t1",
        "mechanism": "survivorship_bias",
        "flagged": True,
        "reason": "x",
    }))
    (bias_dir / "b2.json").write_text(_json.dumps({
        "id": "b2",
        "ts": (_NOW - timedelta(days=200)).isoformat(),
        "thesis_id": "t2",
        "flagged": False,
    }))
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    assert s.bias_checks_in_window == 1


def test_dashboard_renders_text(tmp_path):
    write_cost_of_living_target(
        make_cost_of_living_target(monthly_target=14000.0, region="Bay Area"),
        home=tmp_path,
    )
    write_trade_log(
        make_trade_log(**_csp_kwargs(), ts=_NOW - timedelta(days=5)),
        home=tmp_path,
    )
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    out = render_invest_dashboard(s)
    assert "investment vertical" in out
    assert "Cost-of-living coverage" in out
    assert "Bay Area" in out
    assert "$14,000" in out
    assert "advisory-only" in out


def test_dashboard_renders_empty_state_without_crash(tmp_path):
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    out = render_invest_dashboard(s)
    assert isinstance(out, str)
    assert "unset" in out  # cost-of-living not set
    assert "no trades in window" in out


def test_dashboard_is_frozen(tmp_path):
    s = build_invest_dashboard(home=tmp_path, window_days=30, now=_NOW)
    with pytest.raises(ValidationError):
        s.window_days = 60  # type: ignore[misc]


def test_dashboard_window_days_validated():
    """The Pydantic constraint catches out-of-range windows even
    before the CLI guard fires."""
    with pytest.raises(ValidationError):
        InvestDashboardSummary(
            window_days=0,
            generated_at=_NOW,
        )
    with pytest.raises(ValidationError):
        InvestDashboardSummary(
            window_days=500,
            generated_at=_NOW,
        )
