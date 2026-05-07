"""Tests for ``agent.founder_loop.contract``."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent.founder_loop.contract import (
    bind_morning_contract,
    check_contract,
    load_contract_for_date,
    load_latest_contract,
    save_contract,
)
from agent.founder_loop.priorities import (
    mark_evidenced,
    verify_evidence_shape,
)
from agent.founder_loop.state import Contract, Priority, TankState


def test_bind_morning_contract_basic(tmp_path):
    p = Priority(title="x", evidence_type="commit_pushed",
                 evidence_target="1_commit", weight=2)
    c = bind_morning_contract(
        priorities=[p],
        entertainment_ration_min=60,
        save_to=tmp_path / "contracts.jsonl",
        when=datetime(2026, 5, 5, 9, tzinfo=timezone.utc),
    )
    assert c.date == "2026-05-05"
    assert c.threshold_pct == 90
    # Loadable
    loaded = load_contract_for_date(tmp_path / "contracts.jsonl", "2026-05-05")
    assert loaded is not None
    assert loaded.priorities[0].title == "x"


def test_load_latest_contract_returns_most_recent(tmp_path):
    p = Priority(title="x", evidence_type="commit_pushed",
                 evidence_target="1_commit", weight=1)
    c1 = Contract(date="2026-05-04", priorities=[p],
                  entertainment_ration_min=60,
                  signed_at=datetime(2026, 5, 4, 8, tzinfo=timezone.utc))
    c2 = Contract(date="2026-05-05", priorities=[p],
                  entertainment_ration_min=90,
                  signed_at=datetime(2026, 5, 5, 8, tzinfo=timezone.utc))
    save_contract(c1, tmp_path / "contracts.jsonl")
    save_contract(c2, tmp_path / "contracts.jsonl")
    latest = load_latest_contract(tmp_path / "contracts.jsonl")
    assert latest is not None
    assert latest.date == "2026-05-05"
    assert latest.entertainment_ration_min == 90


def test_check_contract_unlock_below_threshold():
    p = Priority(title="x", evidence_type="commit_pushed",
                 evidence_target="1_commit", weight=1)
    c = Contract(date="2026-05-05", priorities=[p],
                 entertainment_ration_min=60,
                 signed_at=datetime.now(timezone.utc))
    tank = TankState(percent=20, credits_today=20, debits_today=0,
                     threshold=90, ration_remaining_min=60,
                     status="below_threshold")
    chk = check_contract("unlock_entertainment", {}, contract=c, tank=tank)
    assert chk.honored is False
    assert chk.violation_type == "threshold_violation"


def test_check_contract_unlock_within_ration():
    p = Priority(title="x", evidence_type="commit_pushed",
                 evidence_target="1_commit", weight=1)
    c = Contract(date="2026-05-05", priorities=[p],
                 entertainment_ration_min=60,
                 signed_at=datetime.now(timezone.utc))
    tank = TankState(percent=95, credits_today=95, debits_today=0,
                     threshold=90, ration_remaining_min=60,
                     status="threshold_within_ration")
    chk = check_contract("unlock_entertainment", {"duration_min": 30},
                         contract=c, tank=tank)
    assert chk.honored is True


def test_check_contract_block_url_unauthorized_target():
    p = Priority(title="x", evidence_type="commit_pushed",
                 evidence_target="1_commit", weight=1)
    c = Contract(date="2026-05-05", priorities=[p],
                 entertainment_ration_min=60,
                 pre_authorized_blocks=["youtube.com"],
                 signed_at=datetime.now(timezone.utc))
    tank = TankState(percent=80, credits_today=80, debits_today=0,
                     threshold=90, ration_remaining_min=60,
                     status="below_threshold")
    chk = check_contract("block_url", {"target": "https://reddit.com"},
                         contract=c, tank=tank)
    assert chk.honored is False
    assert chk.violation_type == "block_target_not_authorized"


def test_evidence_shape_check_rejects_self_deception():
    """Free-text proof for a structured evidence_type fails."""
    p = Priority(title="x", evidence_type="pr_merged",
                 evidence_target="#142", weight=1)
    ok, _ = verify_evidence_shape(p, "done")
    assert ok is False
    ok2, _ = verify_evidence_shape(p, "#142")
    assert ok2 is True


def test_mark_evidenced_raises_on_bad_proof():
    p = Priority(title="x", evidence_type="pr_merged",
                 evidence_target="#142", weight=1)
    with pytest.raises(ValueError):
        mark_evidenced(p, "trust me bro")
    p2 = mark_evidenced(p, "#142")
    assert p2.status == "evidenced"
    assert p2.evidence_proof == "#142"


def test_warn_over_capacity_doesnt_block():
    """Over-capacity priorities produce a warning, not a refusal.
    Today-self can knowingly accept the over-ambition.
    """
    priorities = [
        Priority(title=f"p{i}", evidence_type="commit_pushed",
                 evidence_target=f"{i}_commits", weight=1)
        for i in range(8)
    ]
    c = bind_morning_contract(priorities=priorities, entertainment_ration_min=60,
                              when=datetime(2026, 5, 5, 9, tzinfo=timezone.utc))
    assert c.notes is not None
    assert "5" in c.notes  # MAX_PRIORITIES_WARN
