"""HTTP-level tests for POST /priority/evidence.

Mirrors tests/test_cli_loop_evidence.py against the daemon route that
backs the /onboard "Mark done" affordance.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Tuple

import pytest

from agent.founder_loop import FounderLoop
from agent.founder_loop.contract import load_latest_contract, save_contract
from agent.founder_loop.observe import FixtureWorkflowxAdapter
from agent.founder_loop.server import serve
from agent.founder_loop.state import Contract, Priority


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post(url: str, body: dict) -> Tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=2.0) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


@pytest.fixture()
def daemon(tmp_path: Path):
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")

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
                    evidence_target="docs/x.md",
                    weight=1,
                ),
            ],
            entertainment_ration_min=60,
            threshold_pct=90,
            signed_at="2026-05-21T08:00:00+00:00",
        ),
        contracts,
    )
    # Bind it via the loop so /chat works downstream if needed.
    loop = FounderLoop(
        registry_path=registry,
        contract_path=contracts,
        adapter=FixtureWorkflowxAdapter(workflowx),
    )
    del loop  # not used; just exercises that the contract path resolves

    port = _free_port()
    server = serve(
        host="127.0.0.1", port=port,
        registry_path=registry,
        contract_path=contracts,
        workflowx_fixture=workflowx,
        block=False,
        research_home=tmp_path / "research",
    )
    base = f"http://127.0.0.1:{port}"

    # Wait until /healthz responds.
    for _ in range(50):
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=0.5):
                break
        except (urllib.error.URLError, OSError):
            time.sleep(0.05)
    else:
        server.shutdown()
        pytest.fail("daemon did not come up within 2.5s")

    yield base, contracts
    server.shutdown()


def test_priority_evidence_marks_priority(daemon) -> None:
    base, contracts = daemon
    status, body = _post(base + "/priority/evidence", {
        "title": "ship daemon",
        "proof": "#44",
    })
    assert status == 200, body
    assert body["ok"] is True
    assert body["already"] is False
    assert body["priority"]["status"] == "evidenced"
    assert body["priority"]["evidence_proof"] == "#44"

    latest = load_latest_contract(contracts)
    assert latest is not None
    target = next(p for p in latest.priorities if "ship daemon" in p.title)
    assert target.status == "evidenced"


def test_priority_evidence_missing_fields(daemon) -> None:
    base, _ = daemon
    status, body = _post(base + "/priority/evidence", {})
    assert status == 400
    assert "required" in body["error"]


def test_priority_evidence_no_match(daemon) -> None:
    base, _ = daemon
    status, body = _post(base + "/priority/evidence", {
        "title": "nonexistent",
        "proof": "#1",
    })
    assert status == 404
    assert "no priority matches" in body["error"]
    assert "candidates" in body


def test_priority_evidence_bad_proof_shape(daemon) -> None:
    base, _ = daemon
    status, body = _post(base + "/priority/evidence", {
        "title": "ship daemon",
        "proof": "done",
    })
    assert status == 400
    assert "does not match" in body["error"]


def test_priority_evidence_idempotent_when_already_evidenced(daemon) -> None:
    base, _ = daemon
    # First call flips.
    _post(base + "/priority/evidence", {
        "title": "ship daemon", "proof": "#44",
    })
    # Second call returns ok+already with no error.
    status, body = _post(base + "/priority/evidence", {
        "title": "ship daemon", "proof": "#44",
    })
    assert status == 200
    assert body["ok"] is True
    assert body["already"] is True


def test_priority_evidence_ambiguous(tmp_path: Path) -> None:
    """Two priorities both matching the needle → 400 with matches list."""
    contracts = tmp_path / "contracts.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")
    save_contract(
        Contract(
            date="2026-05-21",
            priorities=[
                Priority(
                    title="ship daemon UI",
                    evidence_type="pr_merged",
                    evidence_target="#1", weight=1,
                ),
                Priority(
                    title="ship the docs",
                    evidence_type="doc_published",
                    evidence_target="x.md", weight=1,
                ),
            ],
            entertainment_ration_min=60,
            threshold_pct=90,
            signed_at="2026-05-21T08:00:00+00:00",
        ),
        contracts,
    )
    port = _free_port()
    server = serve(
        host="127.0.0.1", port=port,
        registry_path=tmp_path / "registry.jsonl",
        contract_path=contracts,
        workflowx_fixture=workflowx,
        block=False,
        research_home=tmp_path / "research",
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with urllib.request.urlopen(base + "/healthz", timeout=0.5):
                break
        except (urllib.error.URLError, OSError):
            time.sleep(0.05)

    try:
        status, body = _post(base + "/priority/evidence", {
            "title": "ship", "proof": "#1",
        })
        assert status == 400
        assert "ambiguous" in body["error"]
        assert "matches" in body and len(body["matches"]) == 2
    finally:
        server.shutdown()
