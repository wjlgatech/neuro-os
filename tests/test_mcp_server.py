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


def test_server_registers_nine_tools():
    server = build_server()
    tools = asyncio.run(server.list_tools())
    names = sorted(t.name for t in tools)
    assert names == [
        "cross_vertical_query",
        "cross_vertical_share_note",
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
