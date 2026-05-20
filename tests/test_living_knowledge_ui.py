"""
Tests for the Living Knowledge UI routes on the founder_loop daemon.

The daemon now serves:
- GET  /research/living-knowledge          → HTML page
- GET  /research/living-knowledge/data     → JSON (compression + expressions)
- POST /research/living-knowledge/express  → record_expression
- POST /research/living-knowledge/reveal   → reveal_expression
- POST /research/living-knowledge/chat     → brainstorm / interview (single-turn)

Tests spin up the real daemon on a random port and exercise the routes via
urllib so they hit the same code path a browser would. tmp_path is the
research home so the test doesn't pollute ``~/.neuro_os_research/``.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


@pytest.fixture
def daemon(tmp_path, monkeypatch):
    """Spin up the daemon on a random port; point ~/.neuro_os_research at tmp_path.

    Always boots with ANTHROPIC_API_KEY unset so chat-fallback tests are
    deterministic. The daemon caches ``api_key`` at startup; if we waited to
    delenv until inside a test, the LLM path would still be enabled.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from agent.founder_loop.server import serve

    registry = tmp_path / "registry.jsonl"
    registry.write_text("", encoding="utf-8")
    contract = tmp_path / "contracts.jsonl"
    workflowx = tmp_path / "workflowx.jsonl"
    workflowx.write_text("", encoding="utf-8")

    server = serve(
        host="127.0.0.1", port=0,
        registry_path=registry,
        contract_path=contract,
        workflowx_fixture=workflowx,
        block=False,
    )
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}"

    # Wait for daemon ready
    for _ in range(50):
        try:
            urlopen(Request(f"{base}/healthz"), timeout=0.5)
            break
        except Exception:
            time.sleep(0.05)

    yield base, fake_home
    server.shutdown()


def _seed_compression(home: Path):
    """Build + persist a small compression so the UI has something to render."""
    from agent.research.compress import compress_from_synthesis, write_compression
    from agent.research.synthesis import MechanismCluster, SynthesisRun

    research_home = home / ".neuro_os_research"
    research_home.mkdir(parents=True, exist_ok=True)
    cluster = MechanismCluster(
        cluster_id="c1",
        label="Replay buffer",
        mechanism_summary="Selective rehearsal of past experience prevents forgetting.",
        member_card_ids=("card-1", "card-2"),
    )
    run = SynthesisRun(
        run_id="syn-ui-001",
        generated_at=datetime.now(timezone.utc),
        window_days=30,
        min_cluster_size=2,
        method="fallback-heuristic",
        framework_name="(none)",
        input_card_count=2,
        clusters=(cluster,),
        unclustered_card_ids=(),
    )
    compression = compress_from_synthesis(run)
    write_compression(compression, home=research_home)
    return compression


def _get(base, path):
    req = Request(f"{base}{path}")
    req.add_header("Origin", f"http://127.0.0.1:{base.rsplit(':',1)[-1]}")
    return urlopen(req, timeout=5)


def _post(base, path, payload):
    req = Request(
        f"{base}{path}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{base.rsplit(':',1)[-1]}",
        },
    )
    return urlopen(req, timeout=5)


# ---------------------------------------------------------------------------
# GET routes
# ---------------------------------------------------------------------------


def test_living_knowledge_page_served(daemon):
    """The HTML page must load (200, text/html, non-empty)."""
    base, _home = daemon
    resp = _get(base, "/research/living-knowledge")
    assert resp.status == 200
    ct = resp.headers.get("Content-Type", "")
    assert "text/html" in ct
    body = resp.read().decode("utf-8")
    assert "Living Knowledge" in body
    assert "research/living-knowledge/data" in body, (
        "page must wire the data endpoint"
    )


def test_data_endpoint_with_no_compression_returns_explanation(daemon):
    """Cold install: no compression on disk → friendly empty response."""
    base, _ = daemon
    resp = _get(base, "/research/living-knowledge/data")
    data = json.loads(resp.read())
    assert data["compression"] is None
    assert data["expressions"] == []
    assert "no compression yet" in data["reason"]


def test_data_endpoint_returns_seeded_compression(daemon):
    """When a compression exists, it shows up in the data payload."""
    base, home = daemon
    c = _seed_compression(home)
    resp = _get(base, "/research/living-knowledge/data")
    data = json.loads(resp.read())
    assert data["compression"]["compression_id"] == c.compression_id
    assert len(data["compression"]["level_0_nodes"]) == 1
    assert data["expressions"] == []


# ---------------------------------------------------------------------------
# POST /express
# ---------------------------------------------------------------------------


def test_express_round_trip(daemon):
    base, home = daemon
    c = _seed_compression(home)
    l0_id = c.level_0_nodes[0].node_id

    resp = _post(base, "/research/living-knowledge/express", {
        "compression_id": c.compression_id,
        "source_node_id": l0_id,
        "modality": "narrative",
        "title": "Smoke test narrative",
        "content": "A short story testing the daemon route end-to-end.",
        "tool_hint": "markdown",
    })
    expression = json.loads(resp.read())["expression"]
    assert expression["modality"] == "narrative"
    assert expression["source_node_id"] == l0_id
    assert expression["reveals"] is None

    # The data endpoint must now surface it
    data = json.loads(_get(base, "/research/living-knowledge/data").read())
    assert len(data["expressions"]) == 1
    assert data["expressions"][0]["expression_id"] == expression["expression_id"]


def test_express_missing_fields_returns_400(daemon):
    base, home = daemon
    _seed_compression(home)
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/living-knowledge/express", {
            "compression_id": "cmp-anything",
            # missing the rest
        })
    assert exc.value.code == 400
    body = json.loads(exc.value.read())
    assert "missing fields" in body["error"]


def test_express_rejects_unknown_compression(daemon):
    base, home = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/living-knowledge/express", {
            "compression_id": "cmp-does-not-exist",
            "source_node_id": "l0-00",
            "modality": "narrative",
            "title": "x",
            "content": "y",
        })
    assert exc.value.code == 400


def test_express_rejects_unknown_modality(daemon):
    base, home = daemon
    c = _seed_compression(home)
    l0_id = c.level_0_nodes[0].node_id
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/living-knowledge/express", {
            "compression_id": c.compression_id,
            "source_node_id": l0_id,
            "modality": "sonic",  # not in the modality allowlist
            "title": "x",
            "content": "y",
        })
    assert exc.value.code == 400


# ---------------------------------------------------------------------------
# POST /reveal
# ---------------------------------------------------------------------------


def test_reveal_closes_loop_via_daemon(daemon):
    base, home = daemon
    c = _seed_compression(home)
    l0_id = c.level_0_nodes[0].node_id

    expr = json.loads(_post(base, "/research/living-knowledge/express", {
        "compression_id": c.compression_id,
        "source_node_id": l0_id,
        "modality": "musical",
        "title": "Replay harmony",
        "content": "Three voices that fade unless a fourth voice cues them.",
    }).read())["expression"]

    resp = _post(base, "/research/living-knowledge/reveal", {
        "expression_id": expr["expression_id"],
        "insight": "Voices reveal a timing asymmetry the text version hid.",
        "feeds_back_to_node_id": l0_id,
    })
    updated = json.loads(resp.read())["expression"]
    assert updated["expression_id"] == expr["expression_id"]
    assert "timing asymmetry" in updated["reveals"]
    assert updated["feeds_back_to_node_id"] == l0_id

    # Confirm via the data endpoint
    data = json.loads(_get(base, "/research/living-knowledge/data").read())
    assert data["expressions"][0]["reveals"] == updated["reveals"]


def test_reveal_requires_insight_and_id(daemon):
    base, home = daemon
    _seed_compression(home)
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/living-knowledge/reveal", {"expression_id": ""})
    assert exc.value.code == 400


# ---------------------------------------------------------------------------
# POST /chat — brainstorm + interview
# ---------------------------------------------------------------------------


def test_chat_brainstorm_returns_templated_fallback_without_api_key(daemon, monkeypatch):
    """No ANTHROPIC_API_KEY → return a templated reply, not an error."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base, home = daemon
    resp = _post(base, "/research/living-knowledge/chat", {
        "kind": "brainstorm",
        "node_label": "Replay buffer",
        "node_one_sentence": "Selective rehearsal prevents forgetting.",
        "modality": "narrative",
    })
    data = json.loads(resp.read())
    assert data["used_llm"] is False
    assert "STRUCTURAL" in data["reply"] and "INVERTED" in data["reply"]


def test_chat_interview_probe_phase(daemon, monkeypatch):
    """Interview without user_observation = probing-question phase."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base, home = daemon
    resp = _post(base, "/research/living-knowledge/chat", {
        "kind": "interview",
        "node_one_sentence": "Selective rehearsal prevents forgetting.",
        "modality": "narrative",
        "expression_content": "Once upon a time a librarian forgot selectively.",
    })
    data = json.loads(resp.read())
    assert data["used_llm"] is False
    assert "narrative" in data["reply"].lower()


def test_chat_interview_crystallize_phase(daemon, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    base, home = daemon
    resp = _post(base, "/research/living-knowledge/chat", {
        "kind": "interview",
        "node_one_sentence": "Selective rehearsal prevents forgetting.",
        "modality": "narrative",
        "expression_content": "Once upon a time…",
        "user_observation": "the narrative reveals temporal asymmetry",
    })
    data = json.loads(resp.read())
    assert "temporal asymmetry" in data["reply"]


def test_chat_rejects_unknown_kind(daemon):
    base, home = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/living-knowledge/chat", {"kind": "ideate"})
    assert exc.value.code == 400


def test_chat_brainstorm_requires_node_fields(daemon):
    base, home = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/living-knowledge/chat", {
            "kind": "brainstorm",
            "modality": "narrative",
            # missing node_label, node_one_sentence
        })
    assert exc.value.code == 400


# ---------------------------------------------------------------------------
# Cross-origin (security regression — daemon CORS hardening still holds)
# ---------------------------------------------------------------------------


def test_living_knowledge_routes_reject_attacker_origin(daemon):
    """The new routes inherit the daemon's Origin allowlist; attacker.com is rejected."""
    base, home = daemon
    req = Request(f"{base}/research/living-knowledge/data")
    req.add_header("Origin", "http://attacker.com")
    with pytest.raises(HTTPError) as exc:
        urlopen(req, timeout=2)
    assert exc.value.code == 403


def test_living_knowledge_express_rejects_cross_site_post(daemon):
    """CSRF guard: a cross-site POST is rejected before reaching the handler."""
    base, home = daemon
    req = Request(
        f"{base}/research/living-knowledge/express",
        data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    req.add_header("Sec-Fetch-Site", "cross-site")
    with pytest.raises(HTTPError) as exc:
        urlopen(req, timeout=2)
    assert exc.value.code == 403


# ---------------------------------------------------------------------------
# Soft delete + restore (Fix 9 from design audit)
# ---------------------------------------------------------------------------


def test_delete_moves_expression_to_trash(daemon):
    base, home = daemon
    c = _seed_compression(home)
    l0_id = c.level_0_nodes[0].node_id
    expr = json.loads(_post(base, "/research/living-knowledge/express", {
        "compression_id": c.compression_id,
        "source_node_id": l0_id,
        "modality": "narrative",
        "title": "doomed",
        "content": "this one gets deleted",
    }).read())["expression"]

    resp = _post(base, "/research/living-knowledge/delete", {
        "expression_id": expr["expression_id"],
    })
    body = json.loads(resp.read())
    assert body["expression_id"] == expr["expression_id"]
    assert "_trash" in body["trashed_path"]

    # /data must no longer include it
    data = json.loads(_get(base, "/research/living-knowledge/data").read())
    assert all(e["expression_id"] != expr["expression_id"] for e in data["expressions"])


def test_restore_brings_expression_back(daemon):
    base, home = daemon
    c = _seed_compression(home)
    l0_id = c.level_0_nodes[0].node_id
    expr = json.loads(_post(base, "/research/living-knowledge/express", {
        "compression_id": c.compression_id,
        "source_node_id": l0_id,
        "modality": "narrative",
        "title": "second-thoughts",
        "content": "regretted the delete",
    }).read())["expression"]

    # Delete then restore
    _post(base, "/research/living-knowledge/delete", {"expression_id": expr["expression_id"]})
    resp = _post(base, "/research/living-knowledge/restore", {"expression_id": expr["expression_id"]})
    body = json.loads(resp.read())
    assert body["expression_id"] == expr["expression_id"]
    assert "_trash" not in body["restored_path"]

    # /data must include it again
    data = json.loads(_get(base, "/research/living-knowledge/data").read())
    assert any(e["expression_id"] == expr["expression_id"] for e in data["expressions"])


def test_delete_unknown_expression_returns_404(daemon):
    base, _home = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/living-knowledge/delete", {
            "expression_id": "exp-does-not-exist",
        })
    assert exc.value.code == 404


def test_restore_when_not_in_trash_returns_404(daemon):
    base, _home = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/living-knowledge/restore", {
            "expression_id": "exp-never-deleted",
        })
    assert exc.value.code == 404


def test_delete_and_restore_require_expression_id(daemon):
    base, _home = daemon
    for path in ("/research/living-knowledge/delete", "/research/living-knowledge/restore"):
        with pytest.raises(HTTPError) as exc:
            _post(base, path, {})
        assert exc.value.code == 400


# ---------------------------------------------------------------------------
# /queues-restore (Fix 7 from design audit) — client snapshots queues before
# each AI mutation, posts them back when the user clicks Undo.
# ---------------------------------------------------------------------------


def test_queues_restore_writes_files(daemon):
    base, home = daemon
    # Send a snapshot of all three queue files
    payload = {
        "bookmarks_queue": [{"title": "x", "url": "u"}],
        "social_queue": [],
        "rubber_duck_venues": [{"venue": "ec"}],
    }
    resp = _post(base, "/queues-restore", payload)
    body = json.loads(resp.read())
    assert body["restored"] == {
        "bookmarks_queue": 1,
        "social_queue": 0,
        "rubber_duck_venues": 1,
    }
    # Verify on disk via the queues-state endpoint
    state = json.loads(_get(base, "/queues-state").read())
    assert state["bookmarks_queue"] == [{"title": "x", "url": "u"}]
    assert state["social_queue"] == []
    assert state["rubber_duck_venues"] == [{"venue": "ec"}]


def test_queues_restore_rejects_non_list_payload(daemon):
    base, _home = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/queues-restore", {"bookmarks_queue": "not a list"})
    assert exc.value.code == 400


def test_queues_restore_partial_payload_only_writes_named_queues(daemon):
    """If the payload only includes 1 queue, only that queue gets rewritten."""
    base, home = daemon
    # Seed with all three
    _post(base, "/queues-restore", {
        "bookmarks_queue": [{"title": "initial"}],
        "social_queue": [{"name": "initial"}],
        "rubber_duck_venues": [{"venue": "initial"}],
    })
    # Now restore only bookmarks_queue
    _post(base, "/queues-restore", {"bookmarks_queue": []})
    state = json.loads(_get(base, "/queues-state").read())
    assert state["bookmarks_queue"] == []
    assert state["social_queue"] == [{"name": "initial"}]
    assert state["rubber_duck_venues"] == [{"venue": "initial"}]


def test_queues_restore_rejects_cross_site(daemon):
    base, _home = daemon
    req = Request(
        f"{base}/queues-restore", data=b"{}", method="POST",
        headers={"Content-Type": "application/json"},
    )
    req.add_header("Origin", "http://attacker.com")
    with pytest.raises(HTTPError) as exc:
        urlopen(req, timeout=2)
    assert exc.value.code == 403
