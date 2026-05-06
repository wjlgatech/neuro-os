"""
Golden case: "At 2pm I want YouTube before finishing priority work."

This is the V0 acceptance bar in one file. The user logs an urge through
the urge_log surface; the policy honors that user-reported ground truth
over the predictor; the tank reflects acceptance vs override correctly;
and the nightly summary surfaces all four daily-report metrics.

Five small tests pin the loop's behavior on this single canonical
scenario. Each is independent and writes to a tmp_path.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent.founder_loop import (
    Contract,
    FounderLoop,
    Priority,
    UrgeEvent,
    log_urge_event,
    read_recent_urge,
    resolve_urge,
)
from agent.founder_loop.memory import (
    compute_entertainment_usage_min,
    compute_sublimation_success_rate,
)
from agent.founder_loop.observe import RawEvent
from agent.founder_loop.predict import reset_predict_fn, set_predict_fn
from agent.founder_loop.state import ForecastedState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_predictor():
    yield
    reset_predict_fn()


@pytest.fixture
def two_pm() -> datetime:
    """A canonical 2pm UTC timestamp for the golden case."""
    return datetime(2026, 5, 6, 14, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def loop_2pm(tmp_path, two_pm):
    """Build a FounderLoop with a fixture covering the 2pm hour and bind
    today's contract: two priorities, neither evidenced so the tank
    starts well below the threshold (the "before finishing priority
    work" half of the golden-case sentence).
    """
    fixture = tmp_path / "workflowx.jsonl"
    # One hour of activity prior to 2pm: real deep-work, low distraction,
    # rising context switches — the "stuck on the bug" pattern.
    events = [
        RawEvent(
            timestamp=two_pm - timedelta(minutes=m),
            distraction_minutes=2.0,
            deep_work_minutes=3.0,
            context_switches=4,
            sleep_last_night_hours=7.5,
            minutes_since_last_meal=120,
            hours_continuous_screen=3.0,
            last_intent="ship the v0.4 PR",
        )
        for m in range(0, 60, 10)
    ]
    fixture.write_text(
        "\n".join(e.model_dump_json() for e in events) + "\n",
        encoding="utf-8",
    )

    loop = FounderLoop(
        registry_path=tmp_path / "registry.jsonl",
        contract_path=tmp_path / "contracts.jsonl",
        workflowx_export_path=fixture,
        events_path=tmp_path / "founder_events.jsonl",
    )
    loop.morning_ritual(
        priorities=[
            Priority(
                title="ship the v0.4 PR",
                evidence_type="pr_merged",
                evidence_target="neuro-os#142",
                weight=3,
            ),
            Priority(
                title="2 deep-work blocks on predict.py",
                evidence_type="commit_pushed",
                evidence_target="2_commits",
                weight=2,
            ),
        ],
        entertainment_ration_min=60,
        threshold_pct=90,
        when=two_pm.replace(hour=8),
    )
    return loop


# ---------------------------------------------------------------------------
# 1. urge_log round-trip
# ---------------------------------------------------------------------------


def test_log_and_read_recent_urge_round_trip(tmp_path, two_pm):
    """``log_urge_event`` writes; ``read_recent_urge`` reads it back."""
    events_path = tmp_path / "events.jsonl"
    written = log_urge_event(
        urge_type="entertainment",
        context="want to watch YouTube before lunch",
        path=events_path,
        ts=two_pm,
    )
    assert written.urge_type == "entertainment"
    assert written.source == "user_logged"
    assert written.resolved_at is None

    # Within the recency window: returns the urge.
    fetched = read_recent_urge(events_path, now=two_pm + timedelta(minutes=2))
    assert fetched is not None
    assert fetched.id == written.id
    assert fetched.urge_type == "entertainment"

    # Outside the window: returns None.
    stale = read_recent_urge(
        events_path, now=two_pm + timedelta(minutes=30), window_minutes=15
    )
    assert stale is None

    # After resolution, only_unresolved=True excludes it.
    resolve_urge(
        urge_id=written.id,
        resolved_with="constructive_accepted",
        path=events_path,
        ts=two_pm + timedelta(minutes=5),
    )
    after = read_recent_urge(
        events_path, now=two_pm + timedelta(minutes=6), only_unresolved=True
    )
    assert after is None


# ---------------------------------------------------------------------------
# 2. user-logged urge triggers proposal even when predictor says "none"
# ---------------------------------------------------------------------------


def test_user_logged_urge_overrides_predictor_predicting_none(loop_2pm, two_pm):
    """The predictor says no urge — the user disagrees. User wins."""
    # Predictor is silent (predicted_urge='none', need='none').
    set_predict_fn(
        lambda state, intent: ForecastedState(
            predicted_distraction_min=10.0,
            predicted_deep_work_min=30.0,
            predicted_urge="none",
            predicted_underlying_need="none",
            confidence="medium",
            reasoning="No urge signal in the observed window.",
        )
    )

    # User logs the urge.
    loop_2pm.log_urge(
        "entertainment",
        context="want to watch YouTube before finishing the PR",
        when=two_pm - timedelta(minutes=1),
    )
    result = loop_2pm.tick(now=two_pm, dry_run=True)

    # Sublimation branch fired despite predictor='none'.
    assert result.action.op == "propose_constructive_expression"
    assert result.action.payload.get("urge_source") == "user_logged"
    assert "user-logged urge" in result.action.rationale.lower()
    assert result.action.diagnosis is not None
    # With the fixture's signals (sleep=7.5h ok, but rising context switches
    # on a work day with low deep work in the last hour), the catalog
    # router lands on a real underlying need — not 'none'.
    assert result.action.diagnosis.underlying_need != "none"


# ---------------------------------------------------------------------------
# 3. constructive expression has at least one option (criterion #4)
# ---------------------------------------------------------------------------


def test_proposal_includes_at_least_one_constructive_option(loop_2pm, two_pm):
    set_predict_fn(
        lambda state, intent: ForecastedState(
            predicted_distraction_min=15.0,
            predicted_deep_work_min=20.0,
            predicted_urge="entertainment",
            predicted_underlying_need="frustration",
            confidence="medium",
            reasoning="stuck-on-bug pattern.",
        )
    )
    loop_2pm.log_urge("entertainment", context="YouTube?", when=two_pm)
    result = loop_2pm.tick(now=two_pm, dry_run=True)

    assert result.action.op == "propose_constructive_expression"
    diagnosis = result.action.diagnosis
    assert diagnosis is not None
    assert len(diagnosis.options) >= 1
    primary = diagnosis.options[0]
    assert primary.action  # non-empty action label
    assert primary.duration_min >= 1


# ---------------------------------------------------------------------------
# 4. override drains the tank at the abuse-tax rate (criterion #6)
# ---------------------------------------------------------------------------


def test_override_drains_tank_at_abuse_tax_rate(tmp_path, two_pm):
    """A pre-threshold unlock_entertainment with honored=False is taxed.

    Sets up a registry with one over-the-line entertainment row (10min
    consumed pre-threshold) and verifies ``compute_tank`` debits at
    threshold_violation_multiplier × 1pct/min instead of the base rate.
    """
    from agent.founder_loop.contract import bind_morning_contract
    from agent.founder_loop.memory import append_registry_row
    from agent.founder_loop.reward_ledger import compute_tank
    from agent.founder_loop.state import (
        ContractCheck,
        ControlAction,
        FounderState,
        TankState,
    )

    contract = bind_morning_contract(
        priorities=[
            Priority(
                title="ship",
                evidence_type="pr_merged",
                evidence_target="x#1",
                weight=3,
            )
        ],
        entertainment_ration_min=60,
        threshold_pct=90,
        save_to=tmp_path / "contracts.jsonl",
        when=two_pm.replace(hour=8),
    )
    # AbuseTax defaults to 2.0 — so a 10-minute violation should debit
    # 10 * 1pct + 10 * 1pct * (2 - 1) = 20pct (10 base + 10 extra).
    assert contract.abuse_tax.threshold_violation_multiplier == 2.0

    registry = tmp_path / "registry.jsonl"
    state = FounderState(
        timestamp=two_pm,
        distraction_minutes_last_hour=15.0,
        deep_work_minutes_last_hour=20.0,
        context_switches_last_hour=3,
    )
    forecasted = ForecastedState(
        predicted_distraction_min=10.0,
        predicted_deep_work_min=30.0,
        predicted_urge="entertainment",
        predicted_underlying_need="frustration",
        confidence="low",
        reasoning="user proceeded to YouTube anyway.",
    )
    tank = TankState(
        percent=0.0,
        credits_today=0.0,
        debits_today=0.0,
        threshold=90,
        ration_remaining_min=60,
        status="below_threshold",
    )
    action = ControlAction(
        op="unlock_entertainment",
        rationale="user override",
        payload={"duration_min": 10},
        tank_delta=-10.0,
        contract_check=ContractCheck(
            honored=False,
            violation_type="threshold_violation",
        ),
    )
    append_registry_row(
        registry,
        state=state,
        forecasted=forecasted,
        tank=tank,
        action=action,
    )

    rows = json.loads(json.dumps(  # type: ignore[arg-type]
        [json.loads(line) for line in registry.read_text().splitlines()]
    ))
    new_tank = compute_tank(rows, contract=contract)
    # 10min consumed × 1pct/min × 2.0 abuse multiplier = 20pct debit.
    assert new_tank.debits_today == pytest.approx(20.0)
    assert new_tank.percent == 0.0  # clipped at zero
    assert new_tank.status == "below_threshold"


# ---------------------------------------------------------------------------
# 5. nightly summary surfaces all four daily-report metrics (criterion #7)
# ---------------------------------------------------------------------------


def test_nightly_summary_has_all_four_metrics(loop_2pm, two_pm):
    """End-of-day rollup populates MAE, contract-honor, entertainment
    usage, and sublimation success rate.

    Builds three real rows: a propose_constructive_expression
    (sublimation), an unlock_entertainment dishonored (override violation),
    and a continue.
    """
    from agent.founder_loop.memory import append_registry_row
    from agent.founder_loop.state import (
        ContractCheck,
        ControlAction,
        FounderState,
        TankState,
    )

    base_state = FounderState(
        timestamp=two_pm,
        distraction_minutes_last_hour=12.0,
        deep_work_minutes_last_hour=18.0,
        context_switches_last_hour=4,
    )
    base_forecast = ForecastedState(
        predicted_distraction_min=15.0,  # close to 12 actual; small MAE
        predicted_deep_work_min=20.0,
        predicted_urge="entertainment",
        predicted_underlying_need="frustration",
        confidence="medium",
        reasoning="frustration",
    )
    base_tank = TankState(
        percent=10.0,
        credits_today=10.0,
        debits_today=0.0,
        threshold=90,
        ration_remaining_min=60,
        status="below_threshold",
    )

    # 1) Sublimation proposal (counts as denominator for success rate).
    append_registry_row(
        loop_2pm.registry_path,
        state=base_state.model_copy(update={"timestamp": two_pm}),
        forecasted=base_forecast,
        tank=base_tank,
        action=ControlAction(
            op="propose_constructive_expression",
            rationale="frustration; voice memo",
            payload={"primary_action": "voice_memo_to_friend"},
            tank_delta=0.0,
            contract_check=ContractCheck(honored=True),
        ),
    )
    # 2) Override that DID happen after the proposal — proposal "didn't stick".
    append_registry_row(
        loop_2pm.registry_path,
        state=base_state.model_copy(update={"timestamp": two_pm + timedelta(minutes=20)}),
        forecasted=base_forecast,
        tank=base_tank,
        action=ControlAction(
            op="unlock_entertainment",
            rationale="user proceeded",
            payload={"duration_min": 8},
            tank_delta=-8.0,
            contract_check=ContractCheck(
                honored=False, violation_type="threshold_violation"
            ),
        ),
    )
    # 3) A later continue.
    append_registry_row(
        loop_2pm.registry_path,
        state=base_state.model_copy(update={"timestamp": two_pm + timedelta(hours=2)}),
        forecasted=base_forecast,
        tank=base_tank,
        action=ControlAction(
            op="continue",
            rationale="back at work.",
            payload={},
            tank_delta=0.0,
            contract_check=ContractCheck(honored=True),
        ),
    )

    summary = loop_2pm.nightly(day=two_pm)

    # All four metrics populated.
    assert summary.mae_today is not None
    # |15 - 12| = 3, repeated three times across rows = mean 3.0.
    assert summary.mae_today == pytest.approx(3.0)
    assert summary.contract_honor_rate_today is not None
    assert summary.contract_honor_rate_today == pytest.approx(2 / 3)
    assert summary.entertainment_usage_min_today == pytest.approx(8.0)
    # One proposal denominator, the override after it means it didn't
    # stick → success rate = 0/1 = 0.0.
    assert summary.sublimation_success_rate_today == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 6. sublimation_success_rate distinguishes "stuck" from "didn't stick"
# ---------------------------------------------------------------------------


def test_sublimation_success_rate_counts_stuck_proposals():
    """Two proposals, only one followed by a violation → 0.5 rate."""
    rows = [
        {
            "action": {
                "op": "propose_constructive_expression",
                "contract_check": {"honored": True},
            }
        },
        {
            "action": {
                "op": "unlock_entertainment",
                "payload": {"duration_min": 5},
                "contract_check": {
                    "honored": False,
                    "violation_type": "threshold_violation",
                },
            }
        },
        {
            "action": {
                "op": "propose_constructive_expression",
                "contract_check": {"honored": True},
            }
        },
        {
            "action": {
                "op": "continue",
                "contract_check": {"honored": True},
            }
        },
    ]
    rate = compute_sublimation_success_rate(rows)
    assert rate == pytest.approx(0.5)
    usage = compute_entertainment_usage_min(rows)
    assert usage == pytest.approx(5.0)
