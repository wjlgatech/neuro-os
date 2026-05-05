"""Schema-shape pinning tests for ``agent.founder_loop.state``."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agent.founder_loop.state import (
    AbuseTax,
    AUTO_APPLY_DEFAULT,
    AUTO_APPLY_GRADUATABLE,
    Contract,
    ConstructiveExpression,
    ContractCheck,
    ControlAction,
    Diagnosis,
    ForecastedState,
    FounderState,
    Priority,
    TankState,
    TickResult,
)


def test_evidence_type_enforced_by_pydantic():
    with pytest.raises(ValidationError):
        Priority(title="x", evidence_type="vibe_check",
                 evidence_target="y", weight=1)


def test_priority_weight_bounds():
    with pytest.raises(ValidationError):
        Priority(title="x", evidence_type="commit_pushed",
                 evidence_target="1", weight=99)
    Priority(title="x", evidence_type="commit_pushed",
             evidence_target="1", weight=1)
    Priority(title="x", evidence_type="commit_pushed",
             evidence_target="1", weight=3)


def test_underlying_need_vocabulary():
    """Diagnosis enforces the fixed need vocabulary."""
    with pytest.raises(ValidationError):
        Diagnosis(
            underlying_need="enlightenment",  # not in vocab
            confidence="high",
            reasoning="x",
            options=[ConstructiveExpression(action="x", duration_min=10, tank_credit_pct=1.0)],
        )


def test_control_op_vocabulary():
    """ControlAction enforces the fixed op vocabulary."""
    with pytest.raises(ValidationError):
        ControlAction(
            op="meditate",  # not in vocab
            rationale="x",
            contract_check=ContractCheck(honored=True),
        )


def test_auto_apply_default_set():
    """Only `continue` auto-applies in v0; the rest must graduate."""
    assert AUTO_APPLY_DEFAULT == {"continue"}
    assert "force_intent_capture" in AUTO_APPLY_GRADUATABLE
    assert "propose_constructive_expression" in AUTO_APPLY_GRADUATABLE


def test_tank_status_enum():
    """TankState status is fixed-vocab."""
    with pytest.raises(ValidationError):
        TankState(percent=50, credits_today=50, debits_today=0,
                  threshold=90, ration_remaining_min=60,
                  status="unknown_status")


def test_contract_round_trip():
    """Contract serializes and deserializes losslessly."""
    p = Priority(title="x", evidence_type="commit_pushed",
                 evidence_target="1_commit", weight=2)
    c = Contract(
        date="2026-05-05",
        priorities=[p],
        entertainment_ration_min=60,
        signed_at=datetime.now(timezone.utc),
        pre_authorized_blocks=["youtube.com", "twitter.com"],
    )
    s = c.model_dump_json()
    c2 = Contract.model_validate_json(s)
    assert c2.priorities[0].title == "x"
    assert c2.threshold_pct == 90
    assert "youtube.com" in c2.pre_authorized_blocks


def test_constructive_expression_credits_can_be_negative():
    """Negative tank_credit_pct represents a debit (the suppression
    fallback). The schema must allow it.
    """
    e = ConstructiveExpression(action="block_youtube", duration_min=1, tank_credit_pct=-1.0)
    assert e.tank_credit_pct == -1.0


def test_control_action_carries_contract_check():
    """Every ControlAction must have a contract_check (audit invariant)."""
    with pytest.raises(ValidationError):
        ControlAction(op="continue", rationale="x")  # missing contract_check
