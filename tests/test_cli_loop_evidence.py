"""CLI smoke tests for `neuro-os loop evidence`."""
from __future__ import annotations

from pathlib import Path

from agent.cli import main
from agent.founder_loop.contract import load_latest_contract, save_contract
from agent.founder_loop.state import Contract, Priority


def _contract_with_one(tmp_path: Path) -> Path:
    path = tmp_path / "contracts.jsonl"
    save_contract(
        Contract(
            date="2026-05-21",
            priorities=[
                Priority(
                    title="ship daemon UI",
                    evidence_type="pr_merged",
                    evidence_target="neuro-os#44",
                    weight=3,
                ),
                Priority(
                    title="write the docs",
                    evidence_type="doc_published",
                    evidence_target="docs/auto-evidence.md",
                    weight=1,
                ),
            ],
            entertainment_ration_min=60,
            threshold_pct=90,
            signed_at="2026-05-21T08:00:00+00:00",
        ),
        path,
    )
    return path


def test_loop_evidence_marks_priority(tmp_path: Path, capsys) -> None:
    contracts = _contract_with_one(tmp_path)
    rc = main([
        "loop", "evidence", "ship daemon",
        "--proof", "#44",
        "--contracts", str(contracts),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "evidenced: ship daemon UI" in out

    latest = load_latest_contract(contracts)
    assert latest is not None
    target = next(p for p in latest.priorities if p.title == "ship daemon UI")
    assert target.status == "evidenced"
    assert target.evidence_proof == "#44"


def test_loop_evidence_rejects_bad_proof_shape(tmp_path: Path, capsys) -> None:
    contracts = _contract_with_one(tmp_path)
    rc = main([
        "loop", "evidence", "ship daemon",
        "--proof", "done",
        "--contracts", str(contracts),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "does not match" in err

    # Contract unchanged.
    latest = load_latest_contract(contracts)
    assert latest is not None
    target = next(p for p in latest.priorities if p.title == "ship daemon UI")
    assert target.status == "pending"


def test_loop_evidence_no_match(tmp_path: Path, capsys) -> None:
    contracts = _contract_with_one(tmp_path)
    rc = main([
        "loop", "evidence", "nonexistent",
        "--proof", "#1",
        "--contracts", str(contracts),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "no priority matches" in err


def test_loop_evidence_ambiguous(tmp_path: Path, capsys) -> None:
    path = tmp_path / "contracts.jsonl"
    save_contract(
        Contract(
            date="2026-05-21",
            priorities=[
                Priority(
                    title="ship neuro-os",
                    evidence_type="pr_merged",
                    evidence_target="#1",
                    weight=1,
                ),
                Priority(
                    title="ship the docs",
                    evidence_type="doc_published",
                    evidence_target="x.md",
                    weight=1,
                ),
            ],
            entertainment_ration_min=60,
            threshold_pct=90,
            signed_at="2026-05-21T08:00:00+00:00",
        ),
        path,
    )
    rc = main([
        "loop", "evidence", "ship",
        "--proof", "#1",
        "--contracts", str(path),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "ambiguous" in err


def test_loop_evidence_idempotent_when_already_evidenced(
    tmp_path: Path, capsys,
) -> None:
    contracts = _contract_with_one(tmp_path)
    # First call: flips status.
    main([
        "loop", "evidence", "ship daemon",
        "--proof", "#44",
        "--contracts", str(contracts),
    ])
    capsys.readouterr()
    # Second call: no-op.
    rc = main([
        "loop", "evidence", "ship daemon",
        "--proof", "#44",
        "--contracts", str(contracts),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "already evidenced" in out


def test_loop_evidence_no_contract(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "does-not-exist.jsonl"
    rc = main([
        "loop", "evidence", "anything",
        "--proof", "#1",
        "--contracts", str(missing),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "no contract" in err
