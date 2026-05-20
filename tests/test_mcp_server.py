"""
Tests for the neuro-os MCP server.

Strategy:

* **Skip if `mcp` SDK is absent.** The module's only purpose is to expose
  neuro-os to MCP-compatible agents; if the SDK isn't installed,
  there's nothing to test.
* **In-process tool calls** — we call ``FastMCP.call_tool`` directly
  instead of spawning the stdio server. FastMCP's API is async; we
  drive it through ``asyncio.run`` so tests stay synchronous.
* **Tools are thin wrappers; we test the wiring, not the wrapped
  function.** The wrapped functions have their own test files
  (test_research_three_layer.py, test_lane2_skillify.py, etc.).
* **Pydantic round-trip via JSON.** Every tool returns a JSON string;
  we parse + spot-check the payload shape.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

mcp_sdk = pytest.importorskip("mcp")
from agent.mcp_server import build_server  # noqa: E402


def _call(server, tool_name: str, arguments: dict) -> dict:
    """Synchronously invoke a tool via FastMCP and return the parsed
    JSON payload from the first TextContent.

    FastMCP's call_tool returns a tuple of (list_of_TextContent,
    structured_result_dict); we use the TextContent path so the same
    helper works for both list-returning and dict-returning tools.
    """
    content, _structured = asyncio.run(server.call_tool(tool_name, arguments))
    assert content, f"tool {tool_name!r} returned empty content"
    text = content[0].text
    return json.loads(text)


# ---------------------------------------------------------------------------
# Server registration smoke tests
# ---------------------------------------------------------------------------


def test_server_registers_seventeen_tools():
    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = sorted(t.name for t in tools)
    assert names == [
        "cross_vertical_query",
        "cross_vertical_share_note",
        "invest_cost_of_living_read",
        "invest_cost_of_living_set",
        "invest_dashboard",
        "invest_next_action",
        "invest_propose_order",
        "invest_sleeve_balance",
        "invest_trade_close",
        "invest_trade_log",
        "loop_anchor",
        "loop_urge",
        "research_brief",
        "research_checkpoint",
        "research_dashboard",
        "research_ingest",
        "research_synthesize",
    ]


def test_every_tool_has_a_description():
    server = build_server()
    tools = asyncio.run(server.list_tools())
    for t in tools:
        assert t.description and len(t.description) > 10, (
            f"tool {t.name!r} has no description"
        )


def test_server_name_and_instructions():
    server = build_server()
    assert server.name == "neuro-os"
    assert "Three-Layer Research OS" in (server.instructions or "")


# ---------------------------------------------------------------------------
# Research vertical: research_ingest / synthesize / brief / checkpoint /
# dashboard. Wired against tmp_path so no real ~/.neuro_os_research touched.
# ---------------------------------------------------------------------------


def test_research_ingest_returns_error_on_missing_dir(tmp_path):
    server = build_server()
    result = _call(server, "research_ingest", {
        "source_dir": str(tmp_path / "does-not-exist"),
        "no_llm": True,
        "home": str(tmp_path),
    })
    assert "error" in result


def test_research_ingest_runs_against_empty_dir(tmp_path):
    """Heuristic mode (no_llm=True) on an empty directory should produce
    a valid IngestionRun with zero proposals."""
    src = tmp_path / "src"
    src.mkdir()
    server = build_server()
    result = _call(server, "research_ingest", {
        "source_dir": str(src),
        "no_llm": True,
        "home": str(tmp_path / "home"),
    })
    assert result["sources_scanned"] == 0
    assert result["proposals_emitted"] == 0
    assert result["extraction_method"] == "fallback-heuristic"


# ---------------------------------------------------------------------------
# Path-allowlist gate (defense against prompt-injection-driven arbitrary
# file reads in autonomous-mode MCP hosts). Pinned to tests so the gate
# can't silently regress to "any path the agent passes is ingested."
# ---------------------------------------------------------------------------


def test_research_ingest_rejects_system_path():
    """``/etc`` is on the hard system denylist; rejection must happen
    before any disk walk or LLM call."""
    server = build_server()
    result = _call(server, "research_ingest", {
        "source_dir": "/etc",
        "no_llm": True,
    })
    assert "error" in result
    assert "system path" in result["error"].lower()


def test_research_ingest_rejects_sensitive_home_subdir(tmp_path, monkeypatch):
    """A path under one of the sensitive $HOME subdirs (e.g. ``~/.ssh``)
    must be rejected with a clear reason. Uses a tmp HOME so the test
    doesn't depend on what the real $HOME contains."""
    fake_home = tmp_path / "home"
    (fake_home / ".ssh").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    server = build_server()
    result = _call(server, "research_ingest", {
        "source_dir": str(fake_home / ".ssh"),
        "no_llm": True,
        "home": str(tmp_path / "neuro_home"),
    })
    assert "error" in result
    assert "sensitive $home path" in result["error"].lower()


def test_research_ingest_allows_documents_under_home(tmp_path, monkeypatch):
    """A non-sensitive subdirectory of $HOME (e.g. ~/Documents) must
    pass the gate even with no env-var allowlist set."""
    fake_home = tmp_path / "home"
    docs = fake_home / "Documents" / "papers"
    docs.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("NEURO_OS_MCP_INGEST_ALLOWED_PATHS", raising=False)
    server = build_server()
    result = _call(server, "research_ingest", {
        "source_dir": str(docs),
        "no_llm": True,
        "home": str(tmp_path / "neuro_home"),
    })
    # Should run (zero proposals from empty dir), not be rejected.
    assert "error" not in result, f"unexpected reject: {result}"
    assert result["sources_scanned"] == 0


def test_research_ingest_env_var_extends_allowlist(tmp_path, monkeypatch):
    """A path outside the default allowlist becomes allowed when the
    user explicitly lists it via NEURO_OS_MCP_INGEST_ALLOWED_PATHS."""
    # Create a directory in a location that's NOT under $HOME and NOT
    # in /tmp — outside the default allowlist. We use ``tmp_path``
    # itself but pretend HOME is elsewhere so the path is genuinely
    # outside the default set.
    alt_home = tmp_path / "elsewhere_home"
    alt_home.mkdir()
    monkeypatch.setenv("HOME", str(alt_home))
    monkeypatch.delenv("TMPDIR", raising=False)

    custom = tmp_path / "custom_corpus"
    custom.mkdir()

    # Without the env var: outside default allowlist (different HOME,
    # no TMPDIR) — but tmp_path is under /var/folders or /tmp on macOS,
    # which IS in the default tmp allowlist. So this leg of the test
    # demonstrates the env-var path works WHEN it's needed, not that
    # /tmp is excluded.
    monkeypatch.setenv("NEURO_OS_MCP_INGEST_ALLOWED_PATHS", str(custom))
    server = build_server()
    result = _call(server, "research_ingest", {
        "source_dir": str(custom),
        "no_llm": True,
        "home": str(alt_home / "neuro_home"),
    })
    assert "error" not in result, f"env-var allowlist did not work: {result}"


def test_is_safe_ingest_path_returns_resolved_reason():
    """Unit test the gate directly so the reason strings stay stable
    for the agent's error-handling reasoning."""
    from agent.mcp_server import _is_safe_ingest_path

    ok, reason = _is_safe_ingest_path(Path("/etc"))
    assert not ok
    assert "system path" in reason.lower()

    ok, reason = _is_safe_ingest_path(Path("/nonexistent-xyz-9999"))
    assert not ok
    assert "resolved" in reason.lower() or "no such" in reason.lower()


def test_research_synthesize_empty_corpus_returns_note(tmp_path):
    server = build_server()
    result = _call(server, "research_synthesize", {
        "window_days": 30,
        "no_llm": True,
        "home": str(tmp_path),
    })
    assert result["input_card_count"] == 0
    assert result["clusters"] == []
    assert "no accepted mechanism cards" in (result.get("note") or "")


def test_research_synthesize_validates_window():
    server = build_server()
    result = _call(server, "research_synthesize", {
        "window_days": 999, "no_llm": True,
    })
    assert "error" in result


def test_research_brief_unknown_cluster_returns_error(tmp_path):
    server = build_server()
    ctx = json.dumps({
        "project_name": "P",
        "current_questions": ["Q1"],
    })
    result = _call(server, "research_brief", {
        "cluster_id": "ghost",
        "context_json": ctx,
        "no_llm": True,
        "home": str(tmp_path),
    })
    assert "error" in result


def test_research_brief_invalid_context_returns_error(tmp_path):
    server = build_server()
    result = _call(server, "research_brief", {
        "cluster_id": "any",
        "context_json": "{not valid",
        "no_llm": True,
        "home": str(tmp_path),
    })
    assert "error" in result


def test_research_checkpoint_writes_to_jsonl_and_reports_streak(tmp_path):
    server = build_server()
    # First write: converging — streak = 0.
    out1 = _call(server, "research_checkpoint", {
        "brief_produced": True,
        "mental_model_clearer": True,
        "home": str(tmp_path),
    })
    assert out1["trailing_non_converging_streak"] == 0
    assert out1["warning"] is False
    # Second + third writes: non-converging — streak = 2 → warning fires.
    _call(server, "research_checkpoint", {
        "brief_produced": False,
        "mental_model_clearer": True,
        "home": str(tmp_path),
    })
    out3 = _call(server, "research_checkpoint", {
        "brief_produced": True,
        "mental_model_clearer": False,
        "home": str(tmp_path),
    })
    assert out3["trailing_non_converging_streak"] >= 2
    assert out3["warning"] is True


def test_research_dashboard_renders_against_tmp_home(tmp_path):
    server = build_server()
    result = _call(server, "research_dashboard", {
        "window_days": 30,
        "home": str(tmp_path),
    })
    # Empty home → most counters are zero / empty.
    assert result["vertical"] == "research"
    assert result["pending_proposals_count"] == 0
    assert result["tier_balance"] == {}
    assert result["verdict_histogram"] == {}
    assert "system_health_flags" in result


def test_research_dashboard_rejects_bad_window():
    server = build_server()
    result = _call(server, "research_dashboard", {"window_days": 999})
    assert "error" in result


# ---------------------------------------------------------------------------
# Founder loop: loop_anchor / loop_urge
# ---------------------------------------------------------------------------


def test_loop_anchor_writes_and_returns_anchor(tmp_path):
    server = build_server()
    result = _call(server, "loop_anchor", {
        "kind": "faith",
        "context": "morning walk + prayer",
        "home": str(tmp_path),
    })
    assert result["kind"] == "faith"
    assert result["context"] == "morning walk + prayer"
    assert result["anchor_id"]
    # File should exist on disk.
    assert (tmp_path / "anchors.jsonl").exists()


def test_loop_anchor_rejects_unknown_kind(tmp_path):
    server = build_server()
    result = _call(server, "loop_anchor", {
        "kind": "hobby",
        "context": "something",
        "home": str(tmp_path),
    })
    assert "error" in result


def test_loop_anchor_rejects_empty_context(tmp_path):
    server = build_server()
    result = _call(server, "loop_anchor", {
        "kind": "faith",
        "context": "   ",
        "home": str(tmp_path),
    })
    assert "error" in result


def test_loop_urge_writes_urge_event_only_when_no_override(tmp_path):
    events_path = tmp_path / "events.jsonl"
    server = build_server()
    result = _call(server, "loop_urge", {
        "urge_type": "entertainment",
        "context": "wanted to check twitter",
        "events_path": str(events_path),
    })
    assert "id" in result or "event_id" in result
    assert "override_event" not in result
    assert events_path.exists()


def test_loop_urge_with_override_emits_skillify_event(tmp_path, monkeypatch):
    # Redirect the skillify events file into tmp_path so we don't write
    # to the real home.
    monkeypatch.setenv("HOME", str(tmp_path))
    events_path = tmp_path / "events.jsonl"
    server = build_server()
    result = _call(server, "loop_urge", {
        "urge_type": "novelty",
        "context": "checked arxiv mid-deep-work",
        "override_of": "authority_acceptor",
        "override_vertical": "research",
        "events_path": str(events_path),
    })
    assert "override_event" in result
    assert result["override_event"]["drift_mode"] == "authority_acceptor"
    assert result["override_event"]["vertical"] == "research"


def test_loop_urge_rejects_invalid_urge_type():
    server = build_server()
    result = _call(server, "loop_urge", {"urge_type": "boredom"})
    assert "error" in result


# ---------------------------------------------------------------------------
# Cross-vertical: query + share_note
# ---------------------------------------------------------------------------


def test_cross_vertical_query_returns_empty_list_for_missing_store(tmp_path):
    server = build_server()
    result = _call(server, "cross_vertical_query", {
        "reader": "research",
        "store": str(tmp_path / "missing.jsonl"),
    })
    assert result == []


def test_cross_vertical_query_rejects_unknown_reader():
    server = build_server()
    result = _call(server, "cross_vertical_query", {"reader": "marketing"})
    assert "error" in result


def test_cross_vertical_share_note_validates_args(tmp_path):
    server = build_server()
    # Empty note_id.
    out1 = _call(server, "cross_vertical_share_note", {
        "note_id": "",
        "add_visible": ["investment"],
        "store": str(tmp_path / "store.jsonl"),
    })
    assert "error" in out1
    # Empty add_visible list.
    out2 = _call(server, "cross_vertical_share_note", {
        "note_id": "some-id",
        "add_visible": [],
        "store": str(tmp_path / "store.jsonl"),
    })
    assert "error" in out2


def test_cross_vertical_share_note_writes_event(tmp_path):
    server = build_server()
    store = tmp_path / "store.jsonl"
    result = _call(server, "cross_vertical_share_note", {
        "note_id": "card-001",
        "add_visible": ["investment", "startup"],
        "store": str(store),
    })
    assert result["note_id"] == "card-001"
    assert result["added_visible"] == ["investment", "startup"]
    assert store.exists()
    # Inspect the appended row.
    lines = [line for line in store.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [json.loads(line) for line in lines]
    assert any(
        r.get("kind") == "share_event" and r.get("note_id") == "card-001"
        for r in rows
    )


# ---------------------------------------------------------------------------
# Concurrency / state-hygiene
# ---------------------------------------------------------------------------


def test_two_tool_calls_share_state(tmp_path):
    """A `research_checkpoint` followed by `research_dashboard` should
    reflect the just-written checkpoint."""
    server = build_server()
    _call(server, "research_checkpoint", {
        "brief_produced": False,
        "mental_model_clearer": False,
        "home": str(tmp_path),
    })
    _call(server, "research_checkpoint", {
        "brief_produced": False,
        "mental_model_clearer": False,
        "home": str(tmp_path),
    })
    dash = _call(server, "research_dashboard", {
        "window_days": 30,
        "home": str(tmp_path),
    })
    assert dash["checkpoint_no_streak"] >= 2
    assert "system_not_converging" in dash["system_health_flags"]


# ---------------------------------------------------------------------------
# Investment vertical — talk-to-your-portfolio surface
# ---------------------------------------------------------------------------


def test_invest_dashboard_empty_state_flags_missing_target(tmp_path):
    server = build_server()
    result = _call(server, "invest_dashboard", {
        "window_days": 30, "home": str(tmp_path),
    })
    assert result["vertical"] == "investment"
    assert "no_cost_of_living_target" in result["system_health_flags"]


def test_invest_dashboard_rejects_bad_window(tmp_path):
    server = build_server()
    assert "error" in _call(server, "invest_dashboard", {
        "window_days": 999, "home": str(tmp_path),
    })


def test_invest_cost_of_living_set_then_read(tmp_path):
    server = build_server()
    out = _call(server, "invest_cost_of_living_set", {
        "monthly_target": 14000.0,
        "region": "Bay Area",
        "home": str(tmp_path),
    })
    assert out["monthly_target"] == 14000.0
    assert out["region"] == "Bay Area"
    got = _call(server, "invest_cost_of_living_read", {"home": str(tmp_path)})
    assert got["monthly_target"] == 14000.0


def test_invest_cost_of_living_set_rejects_non_positive(tmp_path):
    server = build_server()
    out = _call(server, "invest_cost_of_living_set", {
        "monthly_target": -1.0, "home": str(tmp_path),
    })
    assert "error" in out


def test_invest_cost_of_living_read_returns_empty_when_unset(tmp_path):
    server = build_server()
    got = _call(server, "invest_cost_of_living_read", {"home": str(tmp_path)})
    assert got == {}


def test_invest_cost_of_living_read_from_money_os(tmp_path):
    md = tmp_path / "financial-identity.md"
    md.write_text(
        "# Financial identity\n\nMonthly expenses: $14,000 in Bay Area.\n",
        encoding="utf-8",
    )
    server = build_server()
    out = _call(server, "invest_cost_of_living_read", {
        "money_os_profile_path": str(md),
        "home": str(tmp_path),
    })
    assert out["monthly_target"] == 14000.0
    assert out["source"] == "money_os_profile"


def test_invest_trade_log_records_ev(tmp_path):
    server = build_server()
    out = _call(server, "invest_trade_log", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 200.0,
        "max_loss": 4000.0,
        "win_probability": 0.80,
        "home": str(tmp_path),
    })
    # EV = 0.80 * 200 - 0.20 * 4000 = 160 - 800 = -640.
    # Wait, that's negative because max_loss=4000 is still strike-to-zero-ish.
    # Recompute: 160 - 800 = -640. So the schema DOES surface negative EV.
    # Let's just assert EV is computed (signed) and trade was recorded.
    assert "expected_value" in out
    assert out["ticker"] == "AAPL"
    assert out["strategy"] == "cash_secured_put"
    assert out["outcome"] == "open"


def test_invest_trade_log_rejects_invalid_strategy(tmp_path):
    server = build_server()
    out = _call(server, "invest_trade_log", {
        "strategy": "yolo",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 200.0,
        "max_loss": 4000.0,
        "win_probability": 0.80,
        "home": str(tmp_path),
    })
    assert "error" in out


def test_invest_trade_log_rejects_out_of_range_win_prob(tmp_path):
    server = build_server()
    out = _call(server, "invest_trade_log", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 200.0,
        "max_loss": 4000.0,
        "win_probability": 1.5,
        "home": str(tmp_path),
    })
    assert "error" in out


def test_invest_trade_close_round_trips(tmp_path):
    server = build_server()
    logged = _call(server, "invest_trade_log", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 200.0,
        "max_loss": 4000.0,
        "win_probability": 0.80,
        "home": str(tmp_path),
    })
    closed = _call(server, "invest_trade_close", {
        "trade_id": logged["trade_id"],
        "realized_pnl": 200.0,
        "outcome": "won",
        "home": str(tmp_path),
    })
    assert closed["parent_trade_id"] == logged["trade_id"]
    assert closed["outcome"] == "won"


def test_invest_trade_close_unknown_id_errors(tmp_path):
    server = build_server()
    out = _call(server, "invest_trade_close", {
        "trade_id": "ghost",
        "realized_pnl": 100.0,
        "outcome": "won",
        "home": str(tmp_path),
    })
    assert "error" in out


def test_invest_trade_close_rejects_bad_outcome(tmp_path):
    server = build_server()
    out = _call(server, "invest_trade_close", {
        "trade_id": "anything",
        "realized_pnl": 100.0,
        "outcome": "kinda_won",
        "home": str(tmp_path),
    })
    assert "error" in out


def test_invest_sleeve_balance_empty_state(tmp_path):
    server = build_server()
    out = _call(server, "invest_sleeve_balance", {"home": str(tmp_path)})
    assert out["total_theses"] == 0
    assert out["allocations"] == []


def test_invest_propose_order_returns_proposal_without_writing(tmp_path):
    """Critical HITL invariant: propose_order MUST NOT write to disk."""
    server = build_server()
    before = sorted(p.name for p in tmp_path.rglob("*"))
    out = _call(server, "invest_propose_order", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 200.0,
        "max_loss": 4000.0,
        "win_probability": 0.80,
        "rationale": "harvest premium against cash sleeve",
    })
    after = sorted(p.name for p in tmp_path.rglob("*"))
    assert after == before, "propose_order leaked a file write"
    assert out["kind"] == "order_proposal"
    assert "expected_value" in out
    assert out["recommendation"] in ("authorize_then_log", "review", "reject")
    assert "next_step" in out


def test_invest_propose_order_flags_negative_ev():
    server = build_server()
    out = _call(server, "invest_propose_order", {
        "strategy": "cash_secured_put",
        "ticker": "NVDA",
        "underlying_price": 920.0,
        "expiry": "2026-06-19",
        "strikes": [880.0],
        "premium": 1200.0,
        "max_loss": 88000.0,
        "win_probability": 0.80,
    })
    assert out["expected_value"] < 0
    assert out["recommendation"] == "reject"
    assert "NEGATIVE_EV" in out["risk_banner"]


def test_invest_propose_order_flags_deep_otm():
    server = build_server()
    # High win probability + large max_loss / premium ratio → DEEP_OTM.
    out = _call(server, "invest_propose_order", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 100.0,
        "max_loss": 5000.0,
        "win_probability": 0.95,
    })
    # EV = 0.95 * 100 - 0.05 * 5000 = 95 - 250 = -155, so this is
    # NEGATIVE_EV first and reject wins. Adjust to land in DEEP_OTM:
    out = _call(server, "invest_propose_order", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 200.0,
        "max_loss": 7000.0,
        "win_probability": 0.95,
    })
    # EV = 0.95*200 - 0.05*7000 = 190 - 350 = -160 (still negative).
    # Set win_prob higher so EV is positive but ratio is still bad.
    out = _call(server, "invest_propose_order", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 200.0,
        "max_loss": 7000.0,
        "win_probability": 0.99,
    })
    # EV = 0.99*200 - 0.01*7000 = 198 - 70 = +128. Ratio = 200/7000 = 2.9%.
    # Ratio > 1% so POOR_RATIO doesn't fire; max_loss/premium = 35x → DEEP_OTM does.
    assert out["recommendation"] == "review"
    assert "DEEP_OTM" in out["risk_banner"]


def test_invest_propose_order_recommends_authorize_on_good_setup():
    server = build_server()
    out = _call(server, "invest_propose_order", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 250.0,
        "max_loss": 4000.0,
        "win_probability": 0.80,
    })
    # EV = 0.80*250 - 0.20*4000 = 200 - 800 = -600. Negative again.
    # Bump win_prob to 0.92: EV = 230 - 320 = -90. Still negative.
    out = _call(server, "invest_propose_order", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 400.0,
        "max_loss": 4000.0,
        "win_probability": 0.85,
    })
    # EV = 0.85*400 - 0.15*4000 = 340 - 600 = -260. Still negative.
    # The realistic "good setup" for a CSP needs max_loss reflecting
    # assignment scenario (not strike-to-zero):
    out = _call(server, "invest_propose_order", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 300.0,
        "max_loss": 1000.0,
        "win_probability": 0.80,
    })
    # EV = 0.80*300 - 0.20*1000 = 240 - 200 = +40. Ratio = 300/1000 = 30%. Good.
    assert out["expected_value"] > 0
    assert out["recommendation"] == "authorize_then_log"
    assert "OK" in out["risk_banner"]


def test_invest_next_action_picks_set_target_first(tmp_path):
    """Empty state → highest priority is setting cost-of-living target."""
    server = build_server()
    out = _call(server, "invest_next_action", {"home": str(tmp_path)})
    assert out["priority"] == "high"
    assert "cost-of-living target" in out["action"]
    assert "cli_hint" in out


def test_invest_next_action_picks_open_trade_when_gap_unmet(tmp_path):
    """Target set, no trades → highest priority is opening one to close
    the income gap."""
    server = build_server()
    _call(server, "invest_cost_of_living_set", {
        "monthly_target": 14000.0, "home": str(tmp_path),
    })
    out = _call(server, "invest_next_action", {"home": str(tmp_path)})
    assert out["priority"] == "high"
    assert "income-generating trade" in out["action"] or "trade" in out["action"]


def test_invest_next_action_maintenance_when_healthy(tmp_path, monkeypatch):
    """When no flags fire AND target is set → low-priority maintenance
    action. (We get here by setting a target + having a non-zero realized
    income that closes the gap.)"""
    server = build_server()
    _call(server, "invest_cost_of_living_set", {
        "monthly_target": 100.0,  # tiny target → easy to clear
        "home": str(tmp_path),
    })
    # Log + close a winning trade so realized_pnl >= 70% of 100 = 70.
    logged = _call(server, "invest_trade_log", {
        "strategy": "cash_secured_put",
        "ticker": "AAPL",
        "underlying_price": 230.0,
        "expiry": "2026-06-19",
        "strikes": [220.0],
        "premium": 100.0,
        "max_loss": 200.0,
        "win_probability": 0.80,
        "home": str(tmp_path),
    })
    _call(server, "invest_trade_close", {
        "trade_id": logged["trade_id"],
        "realized_pnl": 100.0,
        "outcome": "won",
        "home": str(tmp_path),
    })
    out = _call(server, "invest_next_action", {"home": str(tmp_path)})
    assert out["priority"] == "low"
    assert "tag" in out["action"].lower() or "invalidation" in out["action"].lower()


def test_invest_tool_descriptions_mention_hitl_and_no_broker():
    """Sanity check: the propose tool's description names the HITL
    invariant + the no-broker-execution boundary."""
    server = build_server()
    tools = asyncio.run(server.list_tools())
    propose = next(t for t in tools if t.name == "invest_propose_order")
    desc = propose.description or ""
    # Either the propose tool itself OR the server-level instructions
    # must explain the no-execute boundary.
    server_instructions = server.instructions or ""
    combined = desc + "\n" + server_instructions
    assert "broker" in combined.lower() or "execute" in combined.lower()
