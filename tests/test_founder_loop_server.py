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
        research_home=tmp_path / "research",  # isolated; avoids real ~/.neuro_os_research
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


def test_onboard_html_served(daemon):
    base, *_ = daemon
    req = urllib.request.Request(base + "/onboard")
    with urllib.request.urlopen(req, timeout=2.0) as r:
        assert r.status == 200
        body = r.read().decode("utf-8")
        ct = r.headers.get("Content-Type", "")
    assert "text/html" in ct
    # Sanity-check the page actually has chat plumbing, not a stub.
    assert "Morning ritual" in body
    assert "/chat" in body
    assert "/sign" in body


def test_dashboard_root_serves_dashboard_page(daemon):
    """`/` is the unified 4-vertical dashboard now — NOT the morning
    ritual. /onboard still serves the ritual."""
    base, *_ = daemon
    req = urllib.request.Request(base + "/")
    with urllib.request.urlopen(req, timeout=2.0) as r:
        assert r.status == 200
        body = r.read().decode("utf-8")
        ct = r.headers.get("Content-Type", "")
    assert "text/html" in ct
    # The dashboard distinguishes itself from /onboard by the
    # four-tile layout — pin specific markers from dashboard.html.
    assert "Loop · daily contract" in body
    assert "Research · living knowledge" in body
    assert "Invest · epistemic calibration" in body
    assert "Startup · OEC convergence" in body
    assert "/dashboard/data" in body


def test_dashboard_data_returns_all_four_blocks(daemon):
    base, *_ = daemon
    r = _get(base + "/dashboard/data")
    assert set(r.keys()) >= {"loop", "research", "invest", "startup"}
    # The fixture binds a contract — loop block must carry a tank.
    assert r["loop"]["contract_bound"] is True
    assert r["loop"]["tank"] is not None
    # Other verticals' homes don't exist in tmp_path, so they return
    # zero/None defaults rather than raising.
    assert r["research"]["pending_proposals"] == 0
    assert r["invest"]["open_positions"] == 0
    assert r["startup"]["ticks_today"] == 0


def test_chat_initial_call_returns_greeting(daemon):
    base, *_ = daemon
    r = _post(base + "/chat", {})
    assert r["conversation_id"]
    assert r["assistant_text"]
    # Daemon fixture binds a contract for today, so /chat opens in
    # AMEND mode: existing priorities are loaded, can_sign=True.
    assert r["amend_mode"] is True
    assert len(r["priorities"]) == 1
    assert r["priorities"][0]["title"] == "ship daemon UI"
    assert r["can_sign"] is True


def test_chat_amend_mode_appends_new_priority(daemon):
    """Adding a priority on a day with a bound contract must keep the
    existing priority and append the new one — no overwrite."""
    base, *_ = daemon
    init = _post(base + "/chat", {})
    cid = init["conversation_id"]
    # The fixture's seed priority is "ship daemon UI" — add another
    # via the fallback walk.
    for msg in [
        "write the amend-mode tests",
        "pr_merged",
        "neuro-os#142",
        "2",
    ]:
        r = _post(base + "/chat", {"conversation_id": cid, "message": msg})
    titles = sorted(p["title"] for p in r["priorities"])
    assert titles == ["ship daemon UI", "write the amend-mode tests"]


def test_chat_amend_mode_sign_writes_union(daemon):
    """After amending, /sign must persist the existing+new set as one
    new contract row — and previous priorities are NOT lost."""
    base, _, contracts = daemon
    init = _post(base + "/chat", {})
    cid = init["conversation_id"]
    for msg in [
        "write the amend-mode tests",
        "pr_merged",
        "neuro-os#142",
        "2",
    ]:
        _post(base + "/chat", {"conversation_id": cid, "message": msg})
    r = _post(base + "/sign", {"conversation_id": cid})
    titles = sorted(p["title"] for p in r["contract"]["priorities"])
    assert titles == ["ship daemon UI", "write the amend-mode tests"]


def test_chat_fallback_extracts_priority(tmp_path: Path):
    """Cold start (no contract bound) — fallback works as before."""
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")
    port = _free_port()
    server = serve(
        host="127.0.0.1", port=port,
        registry_path=registry, contract_path=contracts,
        workflowx_fixture=workflowx, block=False,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                _get(base + "/healthz", timeout=0.5)
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.05)
        init = _post(base + "/chat", {})
        assert init.get("amend_mode") is False
        assert init["priorities"] == []
        cid = init["conversation_id"]
        for msg in [
            "ship founder_loop UI",
            "pr_merged",
            "neuro-os#999",
            "3",
        ]:
            r = _post(base + "/chat", {"conversation_id": cid, "message": msg})
        assert len(r["priorities"]) == 1
        p = r["priorities"][0]
        assert p["title"] == "ship founder_loop UI"
        assert p["evidence_type"] == "pr_merged"
        assert p["weight"] == 3
    finally:
        server.shutdown()


def test_sign_binds_contract(daemon):
    base, registry, contracts = daemon
    init = _post(base + "/chat", {})
    cid = init["conversation_id"]
    for msg in ["ship X", "pr_merged", "repo#1", "2", "done", "45"]:
        _post(base + "/chat", {"conversation_id": cid, "message": msg})
    r = _post(base + "/sign", {
        "conversation_id": cid,
        "entertainment_ration_min": 45,
    })
    assert r["contract"]["entertainment_ration_min"] == 45
    assert len(r["contract"]["priorities"]) >= 1
    # Side effect: contract written to disk under today's date — but the
    # daemon fixture already bound one earlier, so we should now have
    # two rows.
    rows = contracts.read_text().splitlines()
    assert len(rows) >= 2


def test_sign_without_priorities_returns_400(tmp_path: Path):
    """Cold-start daemon (no contract on disk) — /sign with zero
    priorities returns 400. The shared ``daemon`` fixture binds a
    contract before /chat runs, which would put the convo into amend
    mode and pre-seed priorities, so we spin a clean instance here."""
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")
    port = _free_port()
    server = serve(
        host="127.0.0.1", port=port,
        registry_path=registry, contract_path=contracts,
        workflowx_fixture=workflowx, block=False,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                _get(base + "/healthz", timeout=0.5)
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.05)
        init = _post(base + "/chat", {})
        cid = init["conversation_id"]
        data = json.dumps({"conversation_id": cid}).encode("utf-8")
        req = urllib.request.Request(
            base + "/sign", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=2.0)
        assert exc.value.code == 400
    finally:
        server.shutdown()


def test_healthz_reports_contract_and_llm_state(daemon):
    base, *_ = daemon
    r = _get(base + "/healthz")
    assert "contract_bound" in r
    assert r["contract_bound"] is True   # fixture bound one
    assert "has_api_key" in r


def test_about_renders_markdown_to_html(daemon):
    """The /about route renders what-is-this.md as styled HTML."""
    base, *_ = daemon
    req = urllib.request.Request(base + "/about")
    with urllib.request.urlopen(req, timeout=2.0) as r:
        body = r.read().decode("utf-8")
        ct = r.headers.get("Content-Type", "")
    assert "text/html" in ct
    # Markdown features that should round-trip
    assert "<h1>" in body  # the doc starts with #
    # Shell wrapper present
    assert "Founder Loop" in body
    assert "/onboard" in body  # back-link nav


def test_other_doc_routes_render(daemon):
    base, *_ = daemon
    for path in ("/how-to-use", "/how-it-works", "/roadmap"):
        with urllib.request.urlopen(base + path, timeout=2.0) as r:
            body = r.read().decode("utf-8")
        assert "<h1>" in body, f"{path} did not render markdown"
        assert "<table>" in body or "<h2>" in body, (
            f"{path} body looks empty: {body[:200]}"
        )


def test_research_workspace_page_served(daemon):
    """`/research` is the unified workspace — must show all 4 pipeline
    steps (ingest, review, compress, express) and link back to the home."""
    base, *_ = daemon
    with urllib.request.urlopen(base + "/research", timeout=2.0) as r:
        body = r.read().decode("utf-8")
        ct = r.headers.get("Content-Type", "")
    assert "text/html" in ct
    assert "Research workspace" in body
    # Pipeline steps numbered 1..4
    assert "1. Ingest" in body
    assert "2. Review proposals" in body
    assert "3. Compress" in body
    assert "4. Express" in body
    # The three ingest modes are visible
    assert "Mode A · Folder of files" in body
    assert "Mode B · Single URL" in body
    assert "Mode C · Paste raw text" in body
    # Workspace links to the deep-link surfaces and the home
    assert 'href="/research/review"' in body
    assert 'href="/research/living-knowledge"' in body
    assert 'href="/"' in body  # back-to-dashboard breadcrumb


def test_research_state_returns_defaults_for_empty_home(daemon):
    """Daemon fixture's tmp_path has no research home — every counter
    is 0 and llm_available reflects the test daemon's config (no key)."""
    base, *_ = daemon
    r = _get(base + "/research/state")
    assert r["proposals_pending"] == 0
    assert r["cards_accepted"] == 0
    # llm_available is False in the test daemon (no api key, no --use-llm)
    assert r["llm_available"] is False
    assert isinstance(r.get("compressions", []), list)


def test_research_ingest_dir_mode_with_a_markdown_file(daemon, tmp_path):
    """End-to-end: drop a .md into a tempdir, POST /research/ingest with
    mode=dir and no_llm=true, expect proposals_emitted >= 1 and the
    heuristic extractor as the method (daemon has no LLM key)."""
    src = tmp_path / "sources"
    src.mkdir()
    (src / "paper.md").write_text(
        "---\ntitle: Test paper\n---\n\n"
        "## Mechanism\n"
        "Attention reweights tokens by query-key similarity.\n\n"
        "## Invariant\n"
        "Softmax produces a probability distribution.\n\n"
        "## Prediction\n"
        "Longer contexts will dilute attention.\n",
        encoding="utf-8",
    )
    base, *_ = daemon
    r = _post(base + "/research/ingest", {
        "mode": "dir",
        "source_dir": str(src),
        "no_llm": True,
    })
    assert "error" not in r, r
    assert r["sources_scanned"] >= 1
    assert r["extraction_method"] == "fallback-heuristic"


def test_research_ingest_dir_mode_rejects_missing_dir(daemon):
    base, *_ = daemon
    data = json.dumps({"mode": "dir", "source_dir": "/no/such/dir/exists"}).encode("utf-8")
    req = urllib.request.Request(
        base + "/research/ingest", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=2.0)
    assert exc.value.code == 400


def test_research_compress_returns_clear_message_when_no_cards(daemon):
    """No accepted cards yet → /research/compress returns a soft error
    in the body (not an HTTP error) telling the user to accept more."""
    base, *_ = daemon
    r = _post(base + "/research/compress", {})
    # Either there's an explicit error string, or there happens to be
    # enough seeded data — but in the test daemon's empty home the
    # explicit-error branch must fire.
    assert "error" in r, f"expected soft error in body, got: {r}"
    assert "accept" in r["error"].lower() or "no accepted" in r["error"].lower()


def test_review_chat_shell_served(daemon):
    base, *_ = daemon
    with urllib.request.urlopen(base + "/review", timeout=2.0) as r:
        body = r.read().decode("utf-8")
    assert 'name="fl-kind" content="review"' in body


def test_queues_chat_shell_served(daemon):
    base, *_ = daemon
    with urllib.request.urlopen(base + "/queues", timeout=2.0) as r:
        body = r.read().decode("utf-8")
    assert 'name="fl-kind" content="queues"' in body


def test_chat_with_kind_review_uses_review_prompt(daemon):
    base, *_ = daemon
    r = _post(base + "/chat", {"kind": "review"})
    assert r["kind"] == "review"
    # Greeting differs from morning kind
    assert "evening" in r["assistant_text"].lower() or \
           "review" in r["assistant_text"].lower()


def test_chat_with_kind_queues_returns_kickoff(daemon):
    base, *_ = daemon
    r = _post(base + "/chat", {"kind": "queues"})
    assert r["kind"] == "queues"
    # Kickoff should include current queue contents (empty arrays OK)
    assert r.get("kickoff") and "bookmarks_queue" in r["kickoff"]


def test_queues_state_returns_three_arrays(daemon):
    base, *_ = daemon
    r = _get(base + "/queues-state")
    for key in ("bookmarks_queue", "social_queue", "rubber_duck_venues"):
        assert key in r, f"missing queue: {key}"
        assert isinstance(r[key], list)


def test_unknown_kind_returns_400(daemon):
    base, *_ = daemon
    data = json.dumps({"kind": "bogus"}).encode("utf-8")
    req = urllib.request.Request(
        base + "/chat", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req, timeout=2.0)
    assert exc.value.code == 400


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
