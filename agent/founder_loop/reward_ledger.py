"""
``reward_ledger.py`` — the productivity tank.

Pure-function reduce over the day's registry rows + today's contract.
The tank quantifies "how much has today-self earned vs spent" and, via
its three statuses, gates the policy:

* ``below_threshold`` — entertainment is not yet unlocked. Urge-detection
  routes to sublimation.
* ``threshold_within_ration`` — entertainment is unlocked, ration
  remaining. ``unlock_entertainment`` is the right op.
* ``threshold_over_ration`` — entertainment was earned but the daily
  ration is exhausted. Further consumption debits at the abuse-tax rate;
  policy routes residual urge to sublimation again.

Tank math (deliberately simple, easy to audit):

* **Credit.** When a priority flips to ``evidenced``, the tank gains
  ``(priority.weight / total_weight) * 100``. Three priorities of weight
  3+2+1 evidenced fully = 100% tank. Sublimation acceptance also
  credits via the ``ConstructiveExpression.tank_credit_pct`` field.
* **Debit.** Entertainment minutes consumed debit at 1pct/min (default).
  Contract violations multiply that rate by ``abuse_tax``.
* **Status.** Determined by ``percent vs threshold`` and
  ``ration_remaining_min``.

This module is pure: no I/O, no LLM. Reads registry rows as a list of
dicts (the JSONL-decoded form).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from agent.founder_loop.contract import (
    evidenced_priority_weight,
    total_priority_weight,
)
from agent.founder_loop.state import Contract, TankState


# Per-minute entertainment debit rate (% of tank per minute consumed).
# 60min = 60% drop without abuse-tax. Set so that a single ration
# meaningfully drains the tank (so over-rationing crosses thresholds).
_ENTERTAINMENT_DEBIT_PCT_PER_MIN = 1.0


def _entertainment_minutes_consumed(rows: List[Dict]) -> float:
    """Sum entertainment minutes consumed today.

    Counts ``unlock_entertainment`` payload duration (when honored), and
    block-overrides / direct entertainment opens (logged as
    ``ControlAction`` rows with ``op='unlock_entertainment'`` and
    ``contract_check.honored=False``).
    """
    minutes = 0.0
    for row in rows:
        action = row.get("action") or {}
        if action.get("op") != "unlock_entertainment":
            continue
        payload = action.get("payload") or {}
        # When duration_min is missing, treat as 1min (the override-open
        # case where workflowx detects the user opened YouTube but no
        # explicit duration).
        minutes += float(payload.get("duration_min", 1.0) or 0.0)
    return minutes


def _violation_minutes(rows: List[Dict], violation_type: str) -> float:
    """Sum entertainment minutes specifically attributed to a given
    violation type — used to apply the abuse-tax multiplier.
    """
    minutes = 0.0
    for row in rows:
        action = row.get("action") or {}
        if action.get("op") != "unlock_entertainment":
            continue
        check = action.get("contract_check") or {}
        if check.get("honored", True):
            continue
        if check.get("violation_type") != violation_type:
            continue
        payload = action.get("payload") or {}
        minutes += float(payload.get("duration_min", 1.0) or 0.0)
    return minutes


def _sublimation_credits(rows: List[Dict]) -> float:
    """Sum tank credits from sublimation acceptances (and rest ops).

    A sublimation acceptance shows up as a ``ControlAction`` with
    ``op='propose_constructive_expression'`` and ``tank_delta > 0`` —
    the policy layer sets the delta to the chosen option's
    ``tank_credit_pct`` when the user accepts.
    """
    credits = 0.0
    for row in rows:
        action = row.get("action") or {}
        if action.get("op") not in (
            "propose_constructive_expression",
            "rest",
            "start_25min_sprint",
        ):
            continue
        delta = float(action.get("tank_delta", 0.0) or 0.0)
        if delta > 0:
            credits += delta
    return credits


def compute_tank(
    rows: List[Dict],
    *,
    contract: Optional[Contract],
) -> TankState:
    """Compute the current tank state from today's registry rows.

    Returns a default zero-state with status='below_threshold' when
    ``contract`` is None — the loop is in pre-contract debugging mode.
    """
    if contract is None:
        return TankState(
            percent=0.0,
            credits_today=0.0,
            debits_today=0.0,
            threshold=90,
            ration_remaining_min=0,
            status="below_threshold",
        )

    total = total_priority_weight(contract)
    evidenced = evidenced_priority_weight(contract)
    priority_credit_pct = (evidenced / total) * 100.0
    sublimation_credits = _sublimation_credits(rows)

    minutes_used = _entertainment_minutes_consumed(rows)
    threshold_violation_min = _violation_minutes(rows, "threshold_violation")
    ration_violation_min = _violation_minutes(rows, "ration_violation")

    base_debit = minutes_used * _ENTERTAINMENT_DEBIT_PCT_PER_MIN
    threshold_extra = (
        threshold_violation_min
        * _ENTERTAINMENT_DEBIT_PCT_PER_MIN
        * (contract.abuse_tax.threshold_violation_multiplier - 1.0)
    )
    ration_extra = (
        ration_violation_min
        * _ENTERTAINMENT_DEBIT_PCT_PER_MIN
        * (contract.abuse_tax.ration_violation_multiplier - 1.0)
    )
    debits = base_debit + threshold_extra + ration_extra
    credits = priority_credit_pct + sublimation_credits

    percent = max(0.0, min(100.0, credits - debits))
    ration_remaining = max(0, int(contract.entertainment_ration_min - minutes_used))

    if percent < float(contract.threshold_pct):
        status = "below_threshold"
    elif ration_remaining > 0:
        status = "threshold_within_ration"
    else:
        status = "threshold_over_ration"

    return TankState(
        percent=percent,
        credits_today=credits,
        debits_today=debits,
        threshold=contract.threshold_pct,
        ration_remaining_min=ration_remaining,
        status=status,  # type: ignore[arg-type]
    )


__all__ = ["compute_tank"]
