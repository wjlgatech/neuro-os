"""Tests for the 3-gap fix:

1. Daemon ingests append to ingestion_runs.jsonl (was CLI-only).
2. Proposal-level dedup at write time (skip if mechanism+invariant hash
   matches an existing pending or accepted proposal).
3. /research/review/data surfaces ``near_duplicate_proposal_ids`` so the
   review UI can show a badge when two proposals share a mechanism hash.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple

import pytest

from agent.founder_loop.contract import save_contract
from agent.founder_loop.server import serve
from agent.founder_loop.state import Contract, Priority
from agent.research.ontology import IngestionRun, MechanismCardProposal
from agent.research.proposals import (
    compute_mechanism_hash,
    existing_mechanism_hashes,
    proposal_hash,
    write_proposal,
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str) -> Tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=2.0) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def _post(url: str, body: dict) -> Tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Helpers — build a minimal MechanismCardProposal for tests.
# ---------------------------------------------------------------------------

def _make_proposal(
    *,
    pid: str = "test-0001",
    title: str = "Test paper",
    mechanism: str = "Mechanism A operates by X.",
    invariant: str = "Invariant holds when Y.",
    status: str = "pending",
) -> MechanismCardProposal:
    return MechanismCardProposal(
        proposal_id=pid,
        proposed_at=datetime.now(timezone.utc),
        status=status,
        paper_title=title,
        paper_source="local:test.pdf",
        mechanism=mechanism,
        invariant=invariant,
        prediction="If X, then Z.",
        failure_mode="Fails when W.",
        source_id="local:test.pdf:abc123",
        source_excerpt="excerpt",
        extraction_method="llm-anthropic",
        extraction_model="claude-haiku-4-5",
        confidence="high",
        reasoning="reasonable",
        entity_mentions=[],
    )


# ---------------------------------------------------------------------------
# Gap 2 — compute_mechanism_hash
# ---------------------------------------------------------------------------

def test_compute_mechanism_hash_is_deterministic() -> None:
    h1 = compute_mechanism_hash("Foo bar baz.", "Holds always.")
    h2 = compute_mechanism_hash("Foo bar baz.", "Holds always.")
    assert h1 == h2
    assert len(h1) == 16
    assert all(c in "0123456789abcdef" for c in h1)


def test_compute_mechanism_hash_is_case_and_whitespace_insensitive() -> None:
    a = compute_mechanism_hash("Foo Bar Baz.", "Holds always.")
    b = compute_mechanism_hash("foo  bar   baz!", "  HOLDS  ALWAYS  ")
    assert a == b


def test_compute_mechanism_hash_distinguishes_distinct_mechanisms() -> None:
    a = compute_mechanism_hash("Latent replay stores activations.", "x")
    b = compute_mechanism_hash("Elastic weight consolidation uses Fisher.", "x")
    assert a != b


# ---------------------------------------------------------------------------
# Gap 2 — existing_mechanism_hashes + dedup at write
# ---------------------------------------------------------------------------

def test_existing_mechanism_hashes_reads_pending_and_accepted(tmp_path: Path) -> None:
    p1 = _make_proposal(pid="pa-1", mechanism="m1", invariant="i1", status="pending")
    p2 = _make_proposal(pid="pa-2", mechanism="m2", invariant="i2", status="accepted")
    p3 = _make_proposal(pid="pa-3", mechanism="m3", invariant="i3", status="rejected")
    write_proposal(p1, home=tmp_path)
    write_proposal(p2, home=tmp_path)
    write_proposal(p3, home=tmp_path)

    hashes = existing_mechanism_hashes(home=tmp_path)
    assert proposal_hash(p1) in hashes
    assert proposal_hash(p2) in hashes
    # Rejected is excluded by default — we honor the user's reject.
    assert proposal_hash(p3) not in hashes


def test_ingest_skips_duplicate_proposal(tmp_path: Path) -> None:
    """ingest() must not double-write a proposal whose mechanism hash is
    already in pending/accepted, and must report it in
    proposals_skipped_duplicate."""
    from agent.research.ingest import ingest

    source_dir = tmp_path / "papers"
    source_dir.mkdir()
    (source_dir / "a.md").write_text("Paper A content about mechanism alpha.")
    (source_dir / "b.md").write_text("Paper B content about mechanism alpha.")

    # Fake LLM that returns the SAME mechanism for every source — exactly
    # the cross-paper-duplicate failure mode we want to dedup.
    def fake_llm(system_prompt: str, user_text: str):
        return [{
            "mechanism": "Cells communicate by axon firing.",
            "invariant": "Firing is binary.",
            "prediction": "Spike rate scales with input.",
            "failure_mode": "Refractory period limits frequency.",
            "confidence": "high",
            "reasoning": "Identified from text.",
        }]

    run = ingest(source_dir=source_dir, llm_fn=fake_llm, home=tmp_path)
    assert run.sources_scanned == 2
    # Both sources produced 1 proposal each; one should be written, the
    # other skipped as a duplicate.
    assert run.proposals_emitted + run.proposals_skipped_duplicate == 2
    assert run.proposals_emitted == 1
    assert run.proposals_skipped_duplicate == 1


def test_ingestion_run_proposals_skipped_duplicate_default(tmp_path: Path) -> None:
    """Old log rows lack the field; loading them must still succeed."""
    old_row = {
        "run_id": "old-row-1",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:01:00Z",
        "sources_scanned": 1,
        "sources_skipped_unchanged": 0,
        "proposals_emitted": 1,
        "extraction_method": "llm-anthropic",
        "cost_usd_estimate": 0.0,
    }
    parsed = IngestionRun.model_validate(old_row)
    assert parsed.proposals_skipped_duplicate == 0


# ---------------------------------------------------------------------------
# Gap 1 + Gap 3 — daemon end-to-end
# ---------------------------------------------------------------------------

@pytest.fixture()
def daemon(tmp_path: Path):
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")
    save_contract(
        Contract(
            date="2026-05-21",
            priorities=[Priority(
                title="x", evidence_type="pr_merged",
                evidence_target="#1", weight=1,
            )],
            entertainment_ration_min=60, threshold_pct=90,
            signed_at="2026-05-21T08:00:00+00:00",
        ),
        contracts,
    )
    research_home = tmp_path / "research"
    port = _free_port()
    server = serve(
        host="127.0.0.1", port=port,
        registry_path=registry,
        contract_path=contracts,
        workflowx_fixture=workflowx,
        block=False,
        research_home=research_home,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=0.5):
                break
        except (urllib.error.URLError, OSError):
            time.sleep(0.05)
    else:
        server.shutdown()
        pytest.fail("daemon did not come up within 2.5s")
    yield base, research_home, tmp_path
    server.shutdown()


def test_gap1_daemon_ingest_appends_to_ingestion_runs_log(daemon, tmp_path: Path) -> None:
    """A UI-driven ingest must write a row to ingestion_runs.jsonl."""
    base, research_home, _ = daemon

    src = tmp_path / "src-for-ingest"
    src.mkdir()
    (src / "doc.md").write_text(
        "Mechanism: cells communicate by axon firing. "
        "Invariant: firing is binary."
    )

    status, body = _post(base + "/research/ingest", {
        "mode": "dir",
        "source_dir": str(src),
        "no_llm": True,
    })
    assert status == 200, body
    assert "run_id" in body

    log_path = research_home / "ingestion_runs.jsonl"
    assert log_path.exists(), "ingestion_runs.jsonl was not created by the daemon"
    lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["run_id"] == body["run_id"]
    assert row["sources_scanned"] == 1


def test_gap3_review_data_surfaces_near_duplicates(daemon) -> None:
    """Two proposals from DIFFERENT papers sharing a mechanism+invariant
    hash must show up in each other's near_duplicate_proposal_ids."""
    base, research_home, _ = daemon

    # Hand-write two proposals with the same normalized mechanism+invariant
    # but different paper_title — simulates the LLM extracting the same
    # idea from two distinct sources.
    p1 = _make_proposal(
        pid="dup-1", title="Paper A",
        mechanism="Latent replay stores intermediate activations.",
        invariant="Storage of activations is cheaper than raw inputs.",
        status="pending",
    )
    p2 = MechanismCardProposal(
        proposal_id="dup-2",
        proposed_at=datetime.now(timezone.utc),
        status="pending",
        paper_title="Paper B",
        paper_source="local:other.pdf",
        mechanism="Latent replay stores intermediate activations.",
        invariant="Storage of activations is cheaper than raw inputs.",
        prediction="works",
        failure_mode="nope",
        source_id="local:other.pdf:def456",
        source_excerpt="x",
        extraction_method="llm-anthropic",
        extraction_model="claude-haiku-4-5",
        confidence="medium",
        reasoning="ok",
        entity_mentions=[],
    )
    p3 = MechanismCardProposal(
        proposal_id="solo-3",
        proposed_at=datetime.now(timezone.utc),
        status="pending",
        paper_title="Paper C",
        paper_source="local:c.pdf",
        mechanism="Elastic weight consolidation uses Fisher information.",
        invariant="Fisher diagonal is cheap to approximate.",
        prediction="x", failure_mode="y",
        source_id="local:c.pdf:ghi",
        source_excerpt="z",
        extraction_method="llm-anthropic",
        extraction_model="claude-haiku-4-5",
        confidence="medium",
        reasoning="ok", entity_mentions=[],
    )
    write_proposal(p1, home=research_home)
    write_proposal(p2, home=research_home)
    write_proposal(p3, home=research_home)

    status, body = _get(base + "/research/review/data")
    assert status == 200

    by_id = {p["proposal_id"]: p for p in body["pending"]}
    assert "dup-1" in by_id and "dup-2" in by_id and "solo-3" in by_id

    # Each duplicate references the other.
    d1_dups = {d["proposal_id"] for d in by_id["dup-1"]["near_duplicate_proposal_ids"]}
    d2_dups = {d["proposal_id"] for d in by_id["dup-2"]["near_duplicate_proposal_ids"]}
    assert "dup-2" in d1_dups
    assert "dup-1" in d2_dups

    # Solo proposal has no near-dups.
    assert by_id["solo-3"]["near_duplicate_proposal_ids"] == []

    # mechanism_hash is exposed and matches between duplicates.
    assert by_id["dup-1"]["mechanism_hash"] == by_id["dup-2"]["mechanism_hash"]
    assert by_id["dup-1"]["mechanism_hash"] != by_id["solo-3"]["mechanism_hash"]
