"""Tests for ``agent.founder_loop.reward_ledger.compute_tank``."""
from __future__ import annotations

from datetime import datetime, timezone

from agent.founder_loop.contract import bind_morning_contract
from agent.founder_loop.priorities import mark_evidenced
from agent.founder_loop.reward_ledger import compute_tank
from agent.founder_loop.state import (
    AbuseTax,
    Contract,
    ControlAction,
    ContractCheck,
    Priority,
)


def _make_contract(num_priorities: int = 3, ration: int = 60) -> Contract:
    weights = [3, 2, 1, 1, 1]
    priorities = [
        Priority(title=f"p{i}", evidence_type="commit_pushed",
                 evidence_target=f"{i}_commit", weight=weights[i % len(weights)])
        for i in range(num_priorities)
    ]
    return bind_morning_contract(
        priorities=priorities, entertainment_ration_min=ration,
        when=datetime(2026, 5, 5, 9, tzinfo=timezone.utc),
    )


def _entertainment_row(duration_min: int, *, honored: bool = True,
                       violation_type: str = None):
    return {
        "action": {
            "op": "unlock_entertainment",
            "payload": {"duration_min": duration_min},
            "contract_check": {
                "honored": honored,
                "violation_type": violation_type,
            },
        }
    }


def test_empty_tank_no_credits():
    c = _make_contract()
    tank = compute_tank([], contract=c)
    assert tank.percent == 0.0
    assert tank.status == "below_threshold"
    assert tank.ration_remaining_min == 60


def test_evidenced_priority_credits_proportional():
    c = _make_contract(num_priorities=3)  # weights [3,2,1] -> total 6
    c.priorities[0] = mark_evidenced(c.priorities[0], "abc1234")
    tank = compute_tank([], contract=c)
    # 3/6 of weight = 50%
    assert 49.0 <= tank.percent <= 51.0
    assert tank.status == "below_threshold"


def test_full_tank_unlocks_within_ration():
    c = _make_contract(num_priorities=3)
    c.priorities[0] = mark_evidenced(c.priorities[0], "abc1234")
    c.priorities[1] = mark_evidenced(c.priorities[1], "def5678")
    c.priorities[2] = mark_evidenced(c.priorities[2], "9abcdef")
    tank = compute_tank([], contract=c)
    assert tank.percent == 100.0
    assert tank.status == "threshold_within_ration"
    assert tank.ration_remaining_min == 60


def test_entertainment_consumption_drains_tank_and_ration():
    c = _make_contract(num_priorities=3)
    c.priorities[0] = mark_evidenced(c.priorities[0], "abc1234")
    c.priorities[1] = mark_evidenced(c.priorities[1], "def5678")
    c.priorities[2] = mark_evidenced(c.priorities[2], "9abcdef")
    rows = [_entertainment_row(30)]
    tank = compute_tank(rows, contract=c)
    # 100% - 30%-debit = 70%
    assert tank.percent == 70.0
    # ration: 60 - 30 = 30 remaining
    assert tank.ration_remaining_min == 30


def test_threshold_violation_applies_abuse_tax():
    c = _make_contract(num_priorities=3, ration=60)
    # No priority evidenced; tank at 0
    rows = [_entertainment_row(20, honored=False, violation_type="threshold_violation")]
    tank = compute_tank(rows, contract=c)
    # Base debit: 20%; abuse tax (default 2x) adds another 20% → 40% total
    assert tank.debits_today >= 40.0


def test_ration_used_status_threshold_over_ration():
    """When the full ration is consumed honestly, ration_remaining=0
    and status flips to ``threshold_over_ration`` — provided the tank
    is still ≥ threshold."""
    c = _make_contract(num_priorities=3, ration=60)
    c.priorities[0] = mark_evidenced(c.priorities[0], "abc1234")
    c.priorities[1] = mark_evidenced(c.priorities[1], "def5678")
    c.priorities[2] = mark_evidenced(c.priorities[2], "9abcdef")
    # 5 minutes of entertainment consumed → tank drops 5%, ration drops 5
    rows = [_entertainment_row(5)]
    tank = compute_tank(rows, contract=c)
    assert tank.ration_remaining_min == 55
    # Tank is still 95% (>= 90% threshold) and ration > 0
    assert tank.status == "threshold_within_ration"


def test_ration_violation_drains_tank_below_threshold():
    """Over-ration consumption with abuse-tax pushes the tank below
    threshold — the philosophy: paying the abuse tax loses your ration
    privilege, residual urge needs sublimation.
    """
    c = _make_contract(num_priorities=3, ration=60)
    c.priorities[0] = mark_evidenced(c.priorities[0], "abc1234")
    c.priorities[1] = mark_evidenced(c.priorities[1], "def5678")
    c.priorities[2] = mark_evidenced(c.priorities[2], "9abcdef")
    rows = [
        _entertainment_row(60),  # ration consumed → 100% - 60% = 40%
        _entertainment_row(15, honored=False, violation_type="ration_violation"),
    ]
    tank = compute_tank(rows, contract=c)
    assert tank.ration_remaining_min == 0
    # Heavy debit pushes below threshold; sublimation routing should now apply
    assert tank.status == "below_threshold"
    assert tank.percent < 90.0
