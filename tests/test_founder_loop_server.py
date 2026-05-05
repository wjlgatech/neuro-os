"""Smoke tests for the local HTTP daemon (``agent.founder_loop.server``).

Boots the daemon on an ephemeral port against a tempdir registry and a
fixture workflowx file, then hits each route. No external dependencies
beyond stdlib + the project itself.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

import pytest

from agent.founder_loop import FounderLoop, Priority
from agent.founder_loop.observe import FixtureWorkflowxAdapter
from agent.founder_loop.server import serve


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str, timeout: float = 2.0) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(url: str, body: Dict[str, Any], timeout: float = 2.0) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


@pytest.fixture
def daemon(tmp_path: Path):
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")  # empty fixture is valid

    # Bind a contract so /tank / /today have something to compute against.
    loop = FounderLoop(
        registry_path=registry,
        contract_path=contracts,
        adapter=FixtureWorkflowxAdapter(workflowx),
    )
    loop.morning_ritual(
        priorities=[
            Priority(
                title="ship daemon UI",
                evidence_type="pr_merged",
                evidence_target="neuro-os#999",
                weight=3,
            ),
        ],
        entertainment_ration_min=60,
        threshold_pct=90,
    )

    port = _free_port()
    server = serve(
        host="127.0.0.1",
        port=port,
        registry_path=registry,
        contract_path=contracts,
        workflowx_fixture=workflowx,
        block=False,
    )
    base = f"http://127.0.0.1:{port}"

    # Wait until /healthz responds.
    for _ in range(50):
        try:
            _get(base + "/healthz", timeout=0.5)
            break
        except (urllib.error.URLError, OSError):
            time.sleep(0.05)
    else:
        server.shutdown()
        pytest.fail("daemon did not come up within 2.5s")

    yield base, registry, contracts
    server.shutdown()


def test_healthz_returns_ok(daemon):
    base, *_ = daemon
    r = _get(base + "/healthz")
    assert r["ok"] is True
    assert r["service"] == "founder_loop"


def test_tank_returns_pydantic_shape(daemon):
    base, *_ = daemon
    r = _get(base + "/tank")
    assert "tank" in r and r["tank"] is not None
    tank = r["tank"]
    for k in ("percent", "credits_today", "debits_today", "threshold",
              "ration_remaining_min", "status"):
        assert k in tank, f"missing tank field: {k}"


def test_contract_returns_priorities(daemon):
    base, *_ = daemon
    r = _get(base + "/contract")
    assert r["contract"] is not None
    assert isinstance(r["contract"]["priorities"], list)
    assert r["contract"]["priorities"][0]["evidence_type"] == "pr_merged"


def test_tick_dry_run_returns_full_result(daemon):
    base, *_ = daemon
    r = _get(base + "/tick?dry_run=true")
    tick = r["tick"]
    for k in ("state", "forecasted", "tank", "action"):
        assert k in tick, f"missing tick field: {k}"
    assert "op" in tick["action"]


def test_today_composite(daemon):
    base, *_ = daemon
    r = _get(base + "/today")
    assert "date" in r
    assert "tank" in r
    assert "contract" in r
    assert "recent_ticks" in r


def test_diagnose_routes_to_fatigue(daemon):
    base, *_ = daemon
    r = _post(base + "/diagnose", {
        "state": {
            "timestamp": "2026-05-05T15:00:00+00:00",
            "distraction_minutes_last_hour": 35,
            "deep_work_minutes_last_hour": 5,
            "context_switches_last_hour": 4,
            "sleep_last_night_hours": 5.0,
            "day_kind": "work",
        },
        "urge_type": "entertainment",
    })
    diag = r["diagnosis"]
    assert diag["underlying_need"] == "fatigue"
    assert any(o["action"] == "20_min_nap" for o in diag["options"])


def test_events_log_appends(daemon):
    base, registry, _contracts = daemon
    events_path = registry.with_name("events.jsonl")
    if events_path.exists():
        events_path.unlink()
    r = _post(base + "/events", {
        "kind": "accepted_expression",
        "expression_index": 0,
        "diagnosis_need": "fatigue",
    })
    assert r["logged"]["kind"] == "accepted_expression"
    assert events_path.exists()
    rows = events_path.read_text().splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["diagnosis_need"] == "fatigue"


def test_unknown_event_kind_returns_400(daemon):
    base, *_ = daemon
    data = json.dumps({"kind": "bogus"}).encode("utf-8")
    req = urllib.request.Request(
        base + "/events", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=2.0)
    assert exc.value.code == 400


def test_invalid_state_returns_400(daemon):
    base, *_ = daemon
    data = json.dumps({"state": {"day_kind": "weekday"}}).encode("utf-8")
    req = urllib.request.Request(
        base + "/diagnose", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=2.0)
    assert exc.value.code == 400


def test_unknown_route_returns_404(daemon):
    base, *_ = daemon
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(base + "/nope", timeout=2.0)
    assert exc.value.code == 404


def test_serve_refuses_non_loopback(tmp_path: Path):
    """Safety: daemon refuses to bind to a non-loopback host."""
    registry = tmp_path / "r.jsonl"
    contracts = tmp_path / "c.jsonl"
    workflowx = tmp_path / "w.jsonl"
    workflowx.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="non-loopback"):
        serve(
            host="0.0.0.0",
            port=0,
            registry_path=registry,
            contract_path=contracts,
            workflowx_fixture=workflowx,
            block=False,
        )
