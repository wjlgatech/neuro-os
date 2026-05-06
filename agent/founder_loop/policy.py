"""
``policy.py`` — orchestrate contract + tank + predict + sublimate → ControlAction.

This is the decision tree that turns observations into a single typed
action. Order matters — earlier rules trump later rules. The order is
the **policy hierarchy**:

1. **Sensor health** — if observations look dead (all zeros for 4+
   ticks) escalate. Without this, every other rule misfires.
2. **Reasoning gate** — Belief OS flag on the user's intent: escalate
   for human review (UAT #4).
3. **Day-shape negative case** — rest day → ``rest`` (UAT #7).
4. **Reward economy** — when the tank crosses threshold AND ration is
   within range, ``unlock_entertainment`` honestly (UAT scenario E).
5. **Sublimation** — pre-threshold urge fires; diagnose and propose a
   constructive expression (UAT scenarios A, B, C, D, F + #1).
6. **Research rabbit-hole** — predicted research_rabbit_hole on a ship
   day → ``shorten_current_task`` (UAT #2).
7. **Decision-fatigue / over-ambition** — too many priorities, decision
   fatigue predicted → ``force_intent_capture`` with a one-thing
   constraint (UAT #3).
8. **Continue** — default. Always lands here when nothing else fires.

Every action carries a ``contract_check`` (audit) and a ``tank_delta``
(bookkeeping). ``inverse_op`` is set for any op that may auto-apply.

The function is pure: same inputs → same output. I/O happens in
``act.py`` (apply patch) and ``memory.py`` (persist to registry).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from agent.founder_loop import sublimate
from agent.founder_loop.contract import check_contract
from agent.founder_loop.evaluate import IntentFlag
from agent.founder_loop.state import (
    AUTO_APPLY_DEFAULT,
    AUTO_APPLY_GRADUATABLE,
    Contract,
    ControlAction,
    ControlOp,
    Diagnosis,
    ForecastedState,
    FounderState,
    TankState,
    UrgeType,
)
from agent.founder_loop.urge_log import UrgeEvent


_DEAD_SENSOR_HOURS = 4


def _is_dead_sensor(
    rows: List[Dict],
    *,
    now: datetime,
    threshold_hours: int = _DEAD_SENSOR_HOURS,
) -> bool:
    """The last ``threshold_hours`` of registry rows have all-zero observations.

    Used by UAT scenario #8. We require at least ``threshold_hours`` rows
    before firing — fewer than 4 hours of all-zero is just early-day or
    late-night quiet.
    """
    relevant = []
    for row in rows:
        state = row.get("state") or {}
        ts = state.get("timestamp")
        try:
            row_ts = datetime.fromisoformat(ts) if ts else None
        except (TypeError, ValueError):
            continue
        if row_ts is None:
            continue
        if (now - row_ts).total_seconds() <= threshold_hours * 3600:
            relevant.append(state)
    if len(relevant) < threshold_hours:
        return False
    for state in relevant:
        if (
            float(state.get("distraction_minutes_last_hour", 0.0) or 0.0) > 0.0
            or float(state.get("deep_work_minutes_last_hour", 0.0) or 0.0) > 0.0
            or int(state.get("context_switches_last_hour", 0) or 0) > 0
        ):
            return False
    return True


def _select_auto_applied(op: ControlOp, *, graduated: Optional[set] = None) -> bool:
    """Whether to auto-apply ``op`` given the current allowlist.

    ``graduated`` is the per-user set of ops that have crossed the
    5-successive-approval bar (UAT #6). v0 ships ``AUTO_APPLY_DEFAULT =
    {"continue"}``; ``force_intent_capture`` and
    ``propose_constructive_expression`` graduate per-user.
    """
    allowlist = AUTO_APPLY_DEFAULT.copy()
    if graduated:
        allowlist |= (graduated & AUTO_APPLY_GRADUATABLE)
    return op in allowlist


def _inverse(op: ControlOp) -> Optional[ControlOp]:
    """Return the action that would undo ``op``, or None if no inverse."""
    return {
        "block_url": "block_url",  # idempotent: re-applying unblocks via inverse op
        "force_intent_capture": "continue",
        "start_25min_sprint": "continue",
        "propose_constructive_expression": "continue",
        "shorten_current_task": "continue",
        "swap_priority": "swap_priority",
    }.get(op)


def _scenario_2_research_rabbit_hole(
    forecasted: ForecastedState,
    contract: Optional[Contract],
    *,
    graduated: Optional[set] = None,
) -> Optional[ControlAction]:
    """If predict.py landed on research_rabbit_hole on a ship day, shorten."""
    if forecasted.predicted_main_failure_mode != "research_rabbit_hole":
        return None
    return ControlAction(
        op="shorten_current_task",
        rationale=(
            "Predictor surfaced research_rabbit_hole on a ship-flavored "
            "context. Shorten the current task to a 30-min budget so the "
            "rabbit hole has a forced exit."
        ),
        payload={"budget_minutes": 30},
        auto_applied=_select_auto_applied("shorten_current_task", graduated=graduated),
        inverse_op=_inverse("shorten_current_task"),
        tank_delta=0.0,
        contract_check=check_contract(
            "shorten_current_task", {}, contract=contract,
            tank=TankState(
                percent=0.0, credits_today=0.0, debits_today=0.0,
                threshold=90, ration_remaining_min=0, status="below_threshold",
            ),
        ),
    )


def _scenario_3_overambition(
    state: FounderState,
    forecasted: ForecastedState,
    contract: Optional[Contract],
    tank: TankState,
    *,
    graduated: Optional[set] = None,
) -> Optional[ControlAction]:
    """When decision-fatigue is predicted AND the contract has too many
    priorities, surface a force_intent_capture with a one-thing constraint.
    """
    if forecasted.predicted_underlying_need != "decision_fatigue":
        return None
    if contract is None:
        return None
    if len(contract.priorities) <= 3:
        return None
    return ControlAction(
        op="force_intent_capture",
        rationale=(
            f"Contract has {len(contract.priorities)} priorities and the "
            "predictor surfaced decision_fatigue. Pick the SINGLE next "
            "thing for the next 25 minutes; the fatigue is from holding "
            "all options open."
        ),
        payload={"constraint": "max_3_priorities", "current_count": len(contract.priorities)},
        auto_applied=_select_auto_applied("force_intent_capture", graduated=graduated),
        inverse_op=_inverse("force_intent_capture"),
        tank_delta=0.0,
        contract_check=check_contract(
            "force_intent_capture", {}, contract=contract, tank=tank,
        ),
    )


def decide_control(
    *,
    state: FounderState,
    forecasted: ForecastedState,
    tank: TankState,
    intent_flag: Optional[IntentFlag] = None,
    contract: Optional[Contract] = None,
    recent_rows: Optional[List[Dict]] = None,
    graduated_auto_apply: Optional[set] = None,
    recent_urge: Optional[UrgeEvent] = None,
    now: Optional[datetime] = None,
) -> ControlAction:
    """The single policy function. See module docstring for hierarchy.

    ``recent_urge``: when present, treats the user-logged urge as ground
    truth and overrides ``forecasted.predicted_urge`` for the duration
    of the decision. The predicted underlying-need still drives
    diagnosis (the catalog router fills in when prediction is 'none').
    """
    now = now or datetime.now(timezone.utc)
    rows = recent_rows or []
    effective_urge: UrgeType = (
        recent_urge.urge_type if recent_urge is not None else forecasted.predicted_urge
    )
    urge_source_note = (
        f"user-logged urge: {effective_urge}"
        if recent_urge is not None
        else f"predicted urge: {effective_urge}"
    )

    # 1. Sensor health (UAT #8)
    if _is_dead_sensor(rows, now=now):
        return ControlAction(
            op="escalate_to_human",
            rationale=(
                f"Last {_DEAD_SENSOR_HOURS}h of observations are all "
                "zero. Workflowx daemon may be dead. Escalating; do not "
                "trust the loop until sensors are restored."
            ),
            payload={"reason": "dead_sensor", "hours_dark": _DEAD_SENSOR_HOURS},
            auto_applied=False,
            tank_delta=0.0,
            contract_check=check_contract(
                "escalate_to_human", {}, contract=contract, tank=tank,
            ),
        )

    # 2. Belief OS gate (UAT #4)
    if intent_flag and intent_flag.flagged:
        return ControlAction(
            op="escalate_to_human",
            rationale=(
                "Belief OS flagged the user's stated intent for review. "
                f"Mechanism: {intent_flag.mechanism}. "
                f"{(intent_flag.reason or '').strip()}"
            )[:600],
            payload={"belief_os_mechanism": intent_flag.mechanism},
            auto_applied=False,
            tank_delta=0.0,
            contract_check=check_contract(
                "escalate_to_human", {}, contract=contract, tank=tank,
            ),
        )

    # 3. Rest day (UAT #7)
    if state.day_kind == "rest":
        return ControlAction(
            op="rest",
            rationale=(
                "Day is marked as rest. Rest is itself the priority — "
                "entertainment is restorative, not counterfeit."
            ),
            payload={},
            auto_applied=_select_auto_applied("rest", graduated=graduated_auto_apply),
            tank_delta=0.0,
            contract_check=check_contract(
                "rest", {}, contract=contract, tank=tank,
            ),
        )

    # 4. Reward economy: tank earned + within ration (Scenario E first half)
    if (
        tank.status == "threshold_within_ration"
        and effective_urge in ("entertainment", "escape")
    ):
        ration = (
            contract.entertainment_ration_min
            if contract is not None
            else tank.ration_remaining_min
        )
        # Reassess at end of ration (then_reassess_at hook).
        from datetime import timedelta as _td
        return ControlAction(
            op="unlock_entertainment",
            rationale=(
                f"Tank at {tank.percent:.0f}% ≥ threshold "
                f"{tank.threshold}% and ration "
                f"{tank.ration_remaining_min}min remaining. You earned "
                "it. After the timer, the residual urge is usually "
                "post-reward fatigue, not real entertainment desire — "
                "I'll re-diagnose then."
            ),
            payload={
                "duration_min": min(ration, tank.ration_remaining_min),
                "then_reassess_at": (now + _td(minutes=tank.ration_remaining_min)).isoformat(),
            },
            auto_applied=False,
            inverse_op=None,
            tank_delta=-float(min(ration, tank.ration_remaining_min)),
            contract_check=check_contract(
                "unlock_entertainment",
                {"duration_min": min(ration, tank.ration_remaining_min)},
                contract=contract, tank=tank,
            ),
        )

    # 5. Reward economy: tank earned but ration over (Scenario E second half).
    # Surface notify + a residual sublimation diagnosis (post_reward_fatigue
    # is the typical residual).
    if (
        tank.status == "threshold_over_ration"
        and effective_urge in ("entertainment", "escape")
    ):
        residual: Diagnosis = sublimate.diagnose(
            state,
            effective_urge,
            predicted_need=forecasted.predicted_underlying_need or "post_reward_fatigue",
            now=now,
        )
        return ControlAction(
            op="notify_ration_used",
            rationale=(
                "Daily entertainment ration is exhausted. Further "
                "consumption debits at the abuse-tax rate. Re-diagnosed "
                f"residual urge: {residual.underlying_need}."
            ),
            payload={"residual_need": residual.underlying_need},
            auto_applied=False,
            tank_delta=0.0,
            diagnosis=residual,
            contract_check=check_contract(
                "notify_ration_used", {}, contract=contract, tank=tank,
            ),
        )

    # 6. Sublimation (Scenarios A, B, C, D, F + UAT #1).
    if effective_urge != "none":
        d = sublimate.diagnose(
            state,
            effective_urge,
            predicted_need=forecasted.predicted_underlying_need,
            now=now,
        )
        # Pick the option's tank_credit_pct as the prospective tank_delta
        # IF the user accepts. The act layer applies it; if the user
        # refuses, memory.py logs a contract_violation row and the tank
        # debits at the abuse tax.
        prospective_credit = d.options[0].tank_credit_pct if d.options else 0.0
        return ControlAction(
            op="propose_constructive_expression",
            rationale=(
                f"{urge_source_note.capitalize()}. Underlying "
                f"need: {d.underlying_need}. {d.reasoning}"
            ),
            payload={
                "diagnosis": d.underlying_need,
                "options_count": len(d.options),
                "primary_action": d.options[0].action if d.options else None,
                "urge_source": "user_logged" if recent_urge else "predicted",
            },
            auto_applied=_select_auto_applied(
                "propose_constructive_expression", graduated=graduated_auto_apply
            ),
            inverse_op=_inverse("propose_constructive_expression"),
            tank_delta=prospective_credit,
            diagnosis=d,
            contract_check=check_contract(
                "propose_constructive_expression", {}, contract=contract, tank=tank,
            ),
        )

    # 7. Research rabbit-hole shortening (UAT #2)
    rabbit = _scenario_2_research_rabbit_hole(
        forecasted, contract, graduated=graduated_auto_apply,
    )
    if rabbit is not None:
        return rabbit

    # 8. Decision-fatigue + over-ambition (UAT #3)
    overamb = _scenario_3_overambition(
        state, forecasted, contract, tank, graduated=graduated_auto_apply,
    )
    if overamb is not None:
        return overamb

    # Default: continue
    return ControlAction(
        op="continue",
        rationale="No urge predicted; trajectory looks fine. Keep working.",
        payload={},
        auto_applied=_select_auto_applied("continue", graduated=graduated_auto_apply),
        tank_delta=0.0,
        contract_check=check_contract("continue", {}, contract=contract, tank=tank),
    )


__all__ = ["decide_control"]
