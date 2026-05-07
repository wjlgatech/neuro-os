"""
14 user-acceptance-test scenarios for ``agent.founder_loop``.

This is the bar: ``pytest tests/test_founder_loop_uat.py -v`` returns
14 green when the system actually delivers the philosophy in the plan.

Each scenario:
1. Builds a synthetic last-hour ``RawEvent`` window written to a temp
   JSONL fixture.
2. Optionally binds a ``Contract`` so the contract-aware ops fire.
3. Stubs ``predict.predict_next_hour`` with a deterministic
   ``ForecastedState`` so the test isn't network-dependent.
4. Calls ``loop.tick()``.
5. Asserts the action shape from the plan's UAT table.

Numbered tests (#1–#8) are the original brute-force-vocab scenarios
ported to the new architecture. Lettered tests (A–F) are the six new
sublimation-flow scenarios from the user's reframe.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent.founder_loop import FounderLoop, Priority
from agent.founder_loop.observe import RawEvent
from agent.founder_loop.predict import set_predict_fn, reset_predict_fn
from agent.founder_loop.state import ForecastedState
from agent.founder_loop.sublimate import reset_diagnose_fn


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


def _write_fixture(path: Path, events: list[RawEvent]) -> None:
    """Dump RawEvents to a JSONL fixture path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(e.model_dump_json() + "\n")


def _stub_forecast(forecast: ForecastedState):
    """Install a deterministic predictor for the duration of the test."""
    set_predict_fn(lambda state, intent: forecast)


@pytest.fixture(autouse=True)
def _clean_predictor():
    """Reset the predictor + diagnoser stubs after every test."""
    yield
    reset_predict_fn()
    reset_diagnose_fn()


@pytest.fixture
def tmp_loop(tmp_path):
    """Build a FounderLoop wired to per-test temp paths."""
    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text("", encoding="utf-8")
    loop = FounderLoop(
        registry_path=tmp_path / "registry.jsonl",
        contract_path=tmp_path / "contracts.jsonl",
        workflowx_export_path=fixture,
    )
    return loop, fixture


# ---------------------------------------------------------------------------
# Scenario fixtures (per scenario)
# ---------------------------------------------------------------------------


def _events_low_sleep_3pm(now: datetime) -> list[RawEvent]:
    """Tuesday 3pm fade after low sleep — Scenarios #1 and A."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=45),
            distraction_minutes=20.0,
            deep_work_minutes=10.0,
            context_switches=4,
            sleep_last_night_hours=5.0,
            hours_continuous_screen=4.5,
            last_intent="work on the founder_loop predict.py module",
            day_kind="work",
        ),
    ]


def _events_research_rabbit_hole(now: datetime) -> list[RawEvent]:
    """Long deep-work block on tabs/research — Scenario #2."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=30),
            distraction_minutes=5.0,
            deep_work_minutes=50.0,
            context_switches=12,
            sleep_last_night_hours=7.5,
            last_intent="ship the v0.4 PR — research caching strategies",
            day_kind="ship",
        ),
    ]


def _events_overambition(now: datetime) -> list[RawEvent]:
    """Monday morning, decision-fatigue setup — Scenario #3."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=30),
            distraction_minutes=15.0,
            deep_work_minutes=10.0,
            context_switches=8,
            sleep_last_night_hours=7.0,
            last_intent="figure out which of the 8 priorities to do first",
            day_kind="work",
        ),
    ]


def _events_belief_os_intent(now: datetime) -> list[RawEvent]:
    """Intent contains survivorship-bias language — Scenario #4."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=10),
            distraction_minutes=5.0,
            deep_work_minutes=20.0,
            context_switches=2,
            sleep_last_night_hours=7.5,
            last_intent="successful founders dropped out of college so I should drop out too",
            day_kind="work",
        ),
    ]


def _events_rest_day(now: datetime) -> list[RawEvent]:
    """User typed 'rest day' — Scenario #7."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=20),
            distraction_minutes=5.0,
            deep_work_minutes=0.0,
            context_switches=0,
            last_intent="rest day, no work today, recovering",
            day_kind="rest",
        ),
    ]


def _events_twitter_doomscroll(now: datetime) -> list[RawEvent]:
    """Mid-deep-work novelty hunger — Scenario B."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=20),
            distraction_minutes=5.0,
            deep_work_minutes=45.0,
            context_switches=6,
            sleep_last_night_hours=8.0,
            last_intent="grinding through CRUD endpoints",
            day_kind="work",
        ),
    ]


def _events_stuck_on_bug(now: datetime) -> list[RawEvent]:
    """90-min flat output on a hard bug — Scenario C."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=30),
            distraction_minutes=10.0,
            deep_work_minutes=8.0,
            context_switches=0,
            sleep_last_night_hours=7.5,
            last_intent="fix the cache invalidation bug",
            day_kind="work",
        ),
    ]


def _events_sunday_loneliness(now: datetime) -> list[RawEvent]:
    """Sunday afternoon, 48h+ since outbound message — Scenario D."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=30),
            distraction_minutes=30.0,
            deep_work_minutes=2.0,
            context_switches=4,
            sleep_last_night_hours=8.0,
            last_outbound_message_age_h=72.0,
            last_intent="just chilling i guess",
            day_kind="unspecified",
        ),
    ]


def _events_just_shipped(now: datetime) -> list[RawEvent]:
    """Tank just hit 100% via priority evidence — Scenario E."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=10),
            distraction_minutes=2.0,
            deep_work_minutes=55.0,
            context_switches=3,
            sleep_last_night_hours=7.5,
            last_intent="shipped the PR; tired",
            day_kind="ship",
        ),
    ]


def _events_hunger_at_4pm(now: datetime) -> list[RawEvent]:
    """4pm, last meal was at noon, embodied need — Scenario F."""
    return [
        RawEvent(
            timestamp=now - timedelta(minutes=20),
            distraction_minutes=8.0,
            deep_work_minutes=20.0,
            context_switches=2,
            sleep_last_night_hours=8.0,
            time_since_last_meal_min=270,
            last_intent="screen feels boring, idk",
            day_kind="work",
        ),
    ]


def _events_dead_sensors(now: datetime) -> list[RawEvent]:
    """No events at all in the last hour."""
    return []


# ---------------------------------------------------------------------------
# Forecast stubs — deterministic outputs for each scenario
# ---------------------------------------------------------------------------


def _forecast(*, urge="entertainment", need="fatigue",
              distraction=45.0, deep_work=10.0,
              failure_mode=None, confidence="high",
              reasoning="stub"):
    return ForecastedState(
        predicted_distraction_min=distraction,
        predicted_deep_work_min=deep_work,
        predicted_urge=urge,
        predicted_underlying_need=need,
        predicted_main_failure_mode=failure_mode,
        confidence=confidence,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# Scenario #1 — Tuesday afternoon YouTube drift after low sleep
# ---------------------------------------------------------------------------


def test_uat_01_youtube_drift_after_low_sleep(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 5, 15, tzinfo=timezone.utc)
    _write_fixture(fixture, _events_low_sleep_3pm(now))
    loop.morning_ritual(
        priorities=[
            Priority(title="ship v0.4", evidence_type="pr_merged",
                     evidence_target="#142", weight=3),
        ],
        entertainment_ration_min=60,
    )
    _stub_forecast(_forecast(
        urge="entertainment", need="fatigue",
        distraction=50.0, deep_work=8.0,
        failure_mode="youtube_drift",
        reasoning="sleep<6.5h + 3pm + decision latency",
    ))
    result = loop.tick(now=now)
    assert result.action.op == "propose_constructive_expression"
    assert result.action.diagnosis.underlying_need == "fatigue"
    assert any("nap" in o.action for o in result.action.diagnosis.options)


# ---------------------------------------------------------------------------
# Scenario #2 — Research rabbit-hole on a ship day
# ---------------------------------------------------------------------------


def test_uat_02_research_rabbit_hole(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 5, 13, tzinfo=timezone.utc)
    _write_fixture(fixture, _events_research_rabbit_hole(now))
    loop.morning_ritual(
        priorities=[
            Priority(title="ship", evidence_type="pr_merged",
                     evidence_target="#999", weight=3),
        ],
        entertainment_ration_min=60,
    )
    _stub_forecast(_forecast(
        urge="none", need="none",
        distraction=15.0, deep_work=20.0,
        failure_mode="research_rabbit_hole",
        reasoning="long research with no commits",
    ))
    result = loop.tick(now=now)
    assert result.action.op == "shorten_current_task"
    assert result.action.payload["budget_minutes"] <= 30


# ---------------------------------------------------------------------------
# Scenario #3 — Monday over-ambition (8 priorities, capacity for 2)
# ---------------------------------------------------------------------------


def test_uat_03_overambition(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 4, 11, tzinfo=timezone.utc)  # Monday
    _write_fixture(fixture, _events_overambition(now))
    priorities = [
        Priority(title=f"priority_{i}", evidence_type="commit_pushed",
                 evidence_target=f"{i}_commits", weight=1)
        for i in range(1, 9)
    ]
    loop.morning_ritual(priorities=priorities, entertainment_ration_min=60)
    _stub_forecast(_forecast(
        urge="none", need="decision_fatigue",
        distraction=30.0, deep_work=15.0,
        reasoning="8 priorities + Monday morning thrash",
    ))
    result = loop.tick(now=now)
    assert result.action.op == "force_intent_capture"
    assert result.action.payload["constraint"] == "max_3_priorities"


# ---------------------------------------------------------------------------
# Scenario #4 — Belief OS flags the user's intent (FIRST GATE)
# ---------------------------------------------------------------------------


def test_uat_04_belief_os_intent_flagged(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 5, 10, tzinfo=timezone.utc)
    _write_fixture(fixture, _events_belief_os_intent(now))
    loop.morning_ritual(
        priorities=[
            Priority(title="x", evidence_type="commit_pushed",
                     evidence_target="1_commit", weight=1),
        ],
        entertainment_ration_min=60,
    )
    # Forecast doesn't matter — Belief OS gate fires first
    _stub_forecast(_forecast(urge="none", need="none"))
    result = loop.tick(now=now)
    assert result.action.op == "escalate_to_human"
    assert "survivorship_bias" in result.action.rationale.lower() or \
           result.action.payload.get("belief_os_mechanism") == "survivorship_bias"


# ---------------------------------------------------------------------------
# Scenario #5 — Day-7 MAE trends down vs. day-1
# ---------------------------------------------------------------------------


def test_uat_05_mae_trends_down(tmp_loop):
    """Build 7+1 days of synthetic registry rows, then run nightly()."""
    loop, fixture = tmp_loop
    # Inject rows directly into the registry path via memory.append_registry_row
    from agent.founder_loop.memory import append_registry_row
    from agent.founder_loop.state import (
        ContractCheck, FounderState, ForecastedState, ControlAction, TankState,
    )
    # Anchor day-1 exactly 7 days before the nightly-day so
    # ``nightly(day=base7+8h)`` reads day-1 rows via ``day - 7d``.
    base = datetime(2026, 4, 28, 10, tzinfo=timezone.utc)  # day 1
    # Day 1 rows: predicted way off (high error)
    for h in range(8):
        ts = base + timedelta(hours=h)
        s = FounderState(
            timestamp=ts,
            distraction_minutes_last_hour=40.0,
            deep_work_minutes_last_hour=10.0,
            context_switches_last_hour=3,
        )
        f = ForecastedState(
            predicted_distraction_min=5.0,  # error 35
            predicted_deep_work_min=50.0,
            predicted_urge="none",
            predicted_underlying_need="none",
            confidence="low", reasoning="day-1 baseline",
        )
        append_registry_row(
            loop.registry_path,
            state=s, forecasted=f,
            tank=TankState(percent=10, credits_today=10, debits_today=0,
                           threshold=90, ration_remaining_min=60,
                           status="below_threshold"),
            action=ControlAction(op="continue", rationale="x",
                                 contract_check=ContractCheck(honored=True)),
        )
    # Day 7 rows: predicted close (low error)
    base7 = base + timedelta(days=7)
    for h in range(8):
        ts = base7 + timedelta(hours=h)
        s = FounderState(
            timestamp=ts,
            distraction_minutes_last_hour=30.0,
            deep_work_minutes_last_hour=20.0,
            context_switches_last_hour=2,
        )
        f = ForecastedState(
            predicted_distraction_min=28.0,  # error 2
            predicted_deep_work_min=22.0,
            predicted_urge="none",
            predicted_underlying_need="none",
            confidence="medium", reasoning="day-7",
        )
        append_registry_row(
            loop.registry_path,
            state=s, forecasted=f,
            tank=TankState(percent=70, credits_today=70, debits_today=0,
                           threshold=90, ration_remaining_min=60,
                           status="below_threshold"),
            action=ControlAction(op="continue", rationale="x",
                                 contract_check=ContractCheck(honored=True)),
        )
    summary = loop.nightly(day=base7 + timedelta(hours=8))
    assert summary.mae_today is not None
    assert summary.mae_7d_ago is not None
    assert summary.mae_today < summary.mae_7d_ago, \
        f"MAE day-7 ({summary.mae_today}) should be < day-1 ({summary.mae_7d_ago})"


# ---------------------------------------------------------------------------
# Scenario #6 — 5 successive identical approvals graduate to auto-apply
# ---------------------------------------------------------------------------


def test_uat_06_graduation(tmp_path):
    """5 consecutive approvals of the same op promote it into the
    graduated_auto_apply set; the 6th tick auto-applies."""
    from agent.founder_loop.memory import append_registry_row
    from agent.founder_loop.state import (
        ContractCheck, FounderState, ForecastedState, ControlAction, TankState,
    )

    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text("", encoding="utf-8")
    base = datetime(2026, 5, 5, 9, tzinfo=timezone.utc)
    # Append 5 identical force_intent_capture rows with auto_applied=False
    for h in range(5):
        ts = base + timedelta(hours=h)
        append_registry_row(
            tmp_path / "registry.jsonl",
            state=FounderState(timestamp=ts, distraction_minutes_last_hour=10,
                               deep_work_minutes_last_hour=20, context_switches_last_hour=1),
            forecasted=ForecastedState(
                predicted_distraction_min=10, predicted_deep_work_min=20,
                predicted_urge="none", predicted_underlying_need="none",
                confidence="low", reasoning="x",
            ),
            tank=TankState(percent=50, credits_today=50, debits_today=0,
                           threshold=90, ration_remaining_min=60,
                           status="below_threshold"),
            action=ControlAction(op="force_intent_capture", rationale="x",
                                 auto_applied=False,
                                 contract_check=ContractCheck(honored=True)),
            extra={"approval_status": "approved"},
        )
    # Aggregate: 5 approvals of force_intent_capture
    rows = list(open(tmp_path / "registry.jsonl").readlines())
    approvals_by_op: dict[str, int] = {}
    import json as _json
    for line in rows:
        r = _json.loads(line)
        if r.get("approval_status") == "approved":
            op = r["action"]["op"]
            approvals_by_op[op] = approvals_by_op.get(op, 0) + 1
    graduated = {op for op, n in approvals_by_op.items() if n >= 5}
    assert "force_intent_capture" in graduated

    # Now the 6th tick with this op in graduated_auto_apply auto-applies.
    loop = FounderLoop(
        registry_path=tmp_path / "registry.jsonl",
        contract_path=tmp_path / "contracts.jsonl",
        workflowx_export_path=fixture,
        graduated_auto_apply=graduated,
    )
    # Build a state that triggers force_intent_capture
    now = base + timedelta(hours=5)
    _write_fixture(fixture, _events_overambition(now))
    loop.morning_ritual(
        priorities=[Priority(title=f"p{i}", evidence_type="commit_pushed",
                             evidence_target=f"{i}_commits", weight=1) for i in range(1, 9)],
        entertainment_ration_min=60,
    )
    set_predict_fn(lambda s, i: _forecast(
        urge="none", need="decision_fatigue",
        distraction=20, deep_work=10,
    ))
    result = loop.tick(now=now)
    assert result.action.op == "force_intent_capture"
    assert result.action.auto_applied is True


# ---------------------------------------------------------------------------
# Scenario #7 — Holiday: user types "rest day"
# ---------------------------------------------------------------------------


def test_uat_07_rest_day(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 10, 12, tzinfo=timezone.utc)
    _write_fixture(fixture, _events_rest_day(now))
    loop.morning_ritual(
        priorities=[Priority(title="just rest", evidence_type="count_reached",
                             evidence_target="1", weight=1)],
        entertainment_ration_min=120,
    )
    _stub_forecast(_forecast(urge="none", need="none"))
    result = loop.tick(now=now)
    assert result.action.op == "rest"


# ---------------------------------------------------------------------------
# Scenario #8 — workflowx daemon dies for 4h
# ---------------------------------------------------------------------------


def test_uat_08_dead_sensor(tmp_path):
    """Pre-populate 4h of all-zero rows, then tick — should escalate."""
    from agent.founder_loop.memory import append_registry_row
    from agent.founder_loop.state import (
        ContractCheck, FounderState, ForecastedState, ControlAction, TankState,
    )
    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text("", encoding="utf-8")
    base = datetime(2026, 5, 5, 10, tzinfo=timezone.utc)
    for h in range(4):
        ts = base + timedelta(hours=h)
        append_registry_row(
            tmp_path / "registry.jsonl",
            state=FounderState(timestamp=ts, distraction_minutes_last_hour=0,
                               deep_work_minutes_last_hour=0, context_switches_last_hour=0),
            forecasted=ForecastedState(
                predicted_distraction_min=0, predicted_deep_work_min=0,
                predicted_urge="none", predicted_underlying_need="none",
                confidence="low", reasoning="dead",
            ),
            tank=TankState(percent=0, credits_today=0, debits_today=0,
                           threshold=90, ration_remaining_min=60,
                           status="below_threshold"),
            action=ControlAction(op="continue", rationale="x",
                                 contract_check=ContractCheck(honored=True)),
        )
    loop = FounderLoop(
        registry_path=tmp_path / "registry.jsonl",
        contract_path=tmp_path / "contracts.jsonl",
        workflowx_export_path=fixture,
    )
    loop.morning_ritual(
        priorities=[Priority(title="x", evidence_type="commit_pushed",
                             evidence_target="1_commit", weight=1)],
        entertainment_ration_min=60,
    )
    now = base + timedelta(hours=4)
    set_predict_fn(lambda s, i: _forecast(urge="none", need="none"))
    result = loop.tick(now=now)
    assert result.action.op == "escalate_to_human"
    assert result.action.payload.get("reason") == "dead_sensor"


# ---------------------------------------------------------------------------
# Scenario A — full sublimation flow on 3pm fade
# ---------------------------------------------------------------------------


def test_uat_A_3pm_fade_sublimation(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 5, 15, tzinfo=timezone.utc)
    _write_fixture(fixture, _events_low_sleep_3pm(now))
    loop.morning_ritual(
        priorities=[Priority(title="x", evidence_type="commit_pushed",
                             evidence_target="1_commit", weight=1)],
        entertainment_ration_min=60,
    )
    _stub_forecast(_forecast(urge="entertainment", need="fatigue"))
    result = loop.tick(now=now)

    assert result.action.op == "propose_constructive_expression"
    d = result.action.diagnosis
    assert d.underlying_need == "fatigue"
    nap_options = [o for o in d.options if "nap" in o.action]
    assert len(nap_options) >= 1, "fatigue diagnosis must include a nap option"
    assert nap_options[0].tank_credit_pct > 0, \
        "constructive expression must credit the tank"
    assert result.action.contract_check.honored is True, \
        "the proposal itself honors the contract; only refusal violates"


# ---------------------------------------------------------------------------
# Scenario B — 11am Twitter doomscroll (novelty hunger)
# ---------------------------------------------------------------------------


def test_uat_B_novelty_hunger(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 5, 11, tzinfo=timezone.utc)
    _write_fixture(fixture, _events_twitter_doomscroll(now))
    loop.morning_ritual(
        priorities=[Priority(title="endpoints", evidence_type="commit_pushed",
                             evidence_target="3_commits", weight=2)],
        entertainment_ration_min=60,
    )
    _stub_forecast(_forecast(urge="novelty", need="novelty_hunger"))
    result = loop.tick(now=now)
    d = result.action.diagnosis
    assert result.action.op == "propose_constructive_expression"
    assert d.underlying_need == "novelty_hunger"
    # Top option should reference the bookmarks queue
    top = d.options[0]
    assert top.duration_min <= 25
    assert any("Karpathy" in r or "Bret" in r or "@" in r for r in top.references), \
        f"novelty option must reference bookmarks_queue; got refs={top.references}"


# ---------------------------------------------------------------------------
# Scenario C — Stuck-on-bug (frustration → externalize)
# ---------------------------------------------------------------------------


def test_uat_C_frustration_externalize(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 5, 13, tzinfo=timezone.utc)
    _write_fixture(fixture, _events_stuck_on_bug(now))
    loop.morning_ritual(
        priorities=[Priority(title="bug", evidence_type="commit_pushed",
                             evidence_target="1_commit", weight=2)],
        entertainment_ration_min=60,
    )
    _stub_forecast(_forecast(urge="escape", need="frustration"))
    result = loop.tick(now=now)
    d = result.action.diagnosis
    assert result.action.op == "propose_constructive_expression"
    assert d.underlying_need == "frustration"
    # Must propose externalization (voice memo / rubber duck)
    assert any("voice_memo" in o.action or "rubber_duck" in o.action
               for o in d.options)


# ---------------------------------------------------------------------------
# Scenario D — Sunday loneliness (social need)
# ---------------------------------------------------------------------------


def test_uat_D_social_need(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 3, 14, tzinfo=timezone.utc)  # Sunday
    _write_fixture(fixture, _events_sunday_loneliness(now))
    loop.morning_ritual(
        priorities=[Priority(title="rest_or_meet", evidence_type="count_reached",
                             evidence_target="1", weight=1)],
        entertainment_ration_min=120,
    )
    _stub_forecast(_forecast(urge="entertainment", need="social",
                             distraction=40.0, deep_work=5.0))
    result = loop.tick(now=now)
    d = result.action.diagnosis
    assert result.action.op == "propose_constructive_expression"
    assert d.underlying_need == "social"
    # References should include someone from social_queue
    top = d.options[0]
    assert any("Sarah" in r or "Daniel" in r or "Jenny" in r for r in top.references), \
        f"social options must reference social_queue; got refs={top.references}"


# ---------------------------------------------------------------------------
# Scenario E — Just shipped → earned reward (positive case)
# ---------------------------------------------------------------------------


def test_uat_E_earned_reward(tmp_loop):
    """Tank is at 100% via evidenced priority; entertainment unlocks honestly."""
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 5, 16, tzinfo=timezone.utc)
    _write_fixture(fixture, _events_just_shipped(now))
    contract = loop.morning_ritual(
        priorities=[
            Priority(title="ship v0.4", evidence_type="pr_merged",
                     evidence_target="#142", weight=3),
        ],
        entertainment_ration_min=60,
    )
    # Mark the priority as evidenced -> tank should hit 100% on next tick
    from agent.founder_loop.contract import save_contract
    from agent.founder_loop.priorities import mark_evidenced
    contract.priorities[0] = mark_evidenced(contract.priorities[0], "#142")
    save_contract(contract, loop.contract_path)

    _stub_forecast(_forecast(urge="entertainment", need="earned_reward",
                             distraction=10.0, deep_work=5.0))
    result = loop.tick(now=now)
    assert result.action.op == "unlock_entertainment", \
        f"expected unlock_entertainment with full tank; got {result.action.op}"
    assert result.action.payload["duration_min"] == 60
    assert result.tank.status == "threshold_within_ration"
    assert result.action.contract_check.honored is True
    assert "then_reassess_at" in result.action.payload


# ---------------------------------------------------------------------------
# Scenario F — Hunger-as-boredom (embodied need)
# ---------------------------------------------------------------------------


def test_uat_F_embodied_hunger(tmp_loop):
    loop, fixture = tmp_loop
    now = datetime(2026, 5, 5, 16, tzinfo=timezone.utc)
    _write_fixture(fixture, _events_hunger_at_4pm(now))
    loop.morning_ritual(
        priorities=[Priority(title="x", evidence_type="commit_pushed",
                             evidence_target="1_commit", weight=1)],
        entertainment_ration_min=60,
    )
    _stub_forecast(_forecast(urge="entertainment", need="embodied_hunger"))
    result = loop.tick(now=now)
    d = result.action.diagnosis
    assert result.action.op == "propose_constructive_expression"
    assert d.underlying_need == "embodied_hunger"
    top = d.options[0]
    assert top.action == "eat_then_reassess"
    assert top.then_reassess_at is not None, \
        "embodied_hunger option must set then_reassess_at"
