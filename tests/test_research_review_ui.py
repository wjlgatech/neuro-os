"""
Tests for the /research/review daemon routes (Fix 1 from design audit).

The daemon serves:
- GET  /research/review        → HTML page
- GET  /research/review/data   → JSON: { pending, recently_accepted, recently_rejected }
- POST /research/review/accept → write MechanismCard, transition proposal pending → accepted
- POST /research/review/reject → transition pending → rejected

Tests spin up the real daemon on a random port and exercise the routes via
urllib. Proposals are seeded directly via the proposals module so the test
doesn't depend on the ingest pipeline (which would need real PDFs / an LLM).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


@pytest.fixture
def daemon(tmp_path, monkeypatch):
    """Spin up the daemon; isolate HOME so the research home is under tmp_path."""
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
        registry_path=registry, contract_path=contract,
        workflowx_fixture=workflowx,
        block=False,
    )
    port = server.server_address[1]
    base = f"http://127.0.0.1:{port}"

    for _ in range(50):
        try:
            urlopen(Request(f"{base}/healthz"), timeout=0.5)
            break
        except Exception:
            time.sleep(0.05)

    yield base, fake_home
    server.shutdown()


def _seed_pending(home, proposal_id="prop-test-01", **overrides):
    """Write one pending MechanismCardProposal to disk."""
    from agent.research.ontology import MechanismCardProposal
    from agent.research.proposals import write_proposal

    fields = {
        "proposal_id": proposal_id,
        "proposed_at": datetime.now(timezone.utc),
        "paper_title": "Test paper",
        "paper_source": "https://example.com/test",
        "mechanism": "M",
        "invariant": "I",
        "prediction": "P",
        "failure_mode": "F",
        "source_id": "test-source",
        "source_excerpt": "an excerpt",
        "extraction_method": "fallback-heuristic",
        "confidence": "medium",
        "reasoning": "test reasoning",
    }
    fields.update(overrides)
    p = MechanismCardProposal(**fields)
    write_proposal(p, home=home / ".neuro_os_research")
    return p


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


def test_review_page_served(daemon):
    base, _ = daemon
    resp = _get(base, "/research/review")
    assert resp.status == 200
    body = resp.read().decode("utf-8")
    assert "Research review" in body
    assert "/research/review/data" in body


def test_data_endpoint_empty_state(daemon):
    base, _ = daemon
    resp = _get(base, "/research/review/data")
    data = json.loads(resp.read())
    assert data["pending"] == []
    assert data["recently_accepted"] == []
    assert data["recently_rejected"] == []


def test_data_endpoint_returns_pending(daemon):
    base, home = daemon
    _seed_pending(home, "prop-001", paper_title="First paper")
    _seed_pending(home, "prop-002", paper_title="Second paper")
    data = json.loads(_get(base, "/research/review/data").read())
    assert len(data["pending"]) == 2
    pids = sorted(p["proposal_id"] for p in data["pending"])
    assert pids == ["prop-001", "prop-002"]


# ---------------------------------------------------------------------------
# POST /accept
# ---------------------------------------------------------------------------


def test_accept_moves_proposal_and_writes_card(daemon):
    base, home = daemon
    _seed_pending(home, "prop-accept-1", paper_title="To be accepted")
    resp = _post(base, "/research/review/accept", {
        "proposal_id": "prop-accept-1",
        "entity_mentions": [],
    })
    data = json.loads(resp.read())
    assert data["accepted_proposal_id"] == "prop-accept-1"
    assert data["card_id"] == "prop-accept-1"
    # /data must no longer list it in pending
    after = json.loads(_get(base, "/research/review/data").read())
    assert all(p["proposal_id"] != "prop-accept-1" for p in after["pending"])
    # ... but it shows up in recently_accepted
    assert any(p["proposal_id"] == "prop-accept-1" for p in after["recently_accepted"])
    # MechanismCard file exists
    card_path = (
        home / ".neuro_os_research" / "mechanism_cards" / "prop-accept-1.json"
    )
    assert card_path.is_file()


def test_accept_with_entity_mentions(daemon):
    base, home = daemon
    _seed_pending(home, "prop-ent-1", paper_title="Entity test")
    resp = _post(base, "/research/review/accept", {
        "proposal_id": "prop-ent-1",
        "entity_mentions": ["Nicholas-Yang", "  Value-Investing  ", ""],
    })
    data = json.loads(resp.read())
    # Mentions get normalized to lowercase + stripped
    assert data["entity_mentions"] == ["nicholas-yang", "value-investing"]


def test_accept_rejects_missing_proposal_id(daemon):
    base, _ = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/review/accept", {})
    assert exc.value.code == 400


def test_accept_404_when_proposal_not_pending(daemon):
    base, home = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/review/accept", {
            "proposal_id": "prop-does-not-exist",
            "entity_mentions": [],
        })
    assert exc.value.code == 404


def test_accept_rejects_non_list_entity_mentions(daemon):
    base, home = daemon
    _seed_pending(home, "prop-bad-ent", paper_title="x")
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/review/accept", {
            "proposal_id": "prop-bad-ent",
            "entity_mentions": "not-a-list",
        })
    assert exc.value.code == 400


# ---------------------------------------------------------------------------
# POST /reject
# ---------------------------------------------------------------------------


def test_reject_moves_proposal(daemon):
    base, home = daemon
    _seed_pending(home, "prop-rej-1", paper_title="To be rejected")
    resp = _post(base, "/research/review/reject", {
        "proposal_id": "prop-rej-1",
    })
    data = json.loads(resp.read())
    assert data["rejected_proposal_id"] == "prop-rej-1"
    after = json.loads(_get(base, "/research/review/data").read())
    assert all(p["proposal_id"] != "prop-rej-1" for p in after["pending"])
    assert any(p["proposal_id"] == "prop-rej-1" for p in after["recently_rejected"])


def test_reject_404_when_not_pending(daemon):
    base, _ = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/review/reject", {"proposal_id": "nope"})
    assert exc.value.code == 404


def test_reject_requires_proposal_id(daemon):
    base, _ = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/review/reject", {})
    assert exc.value.code == 400


# ---------------------------------------------------------------------------
# POST /edit
# ---------------------------------------------------------------------------


def test_edit_updates_pending_fields(daemon):
    base, home = daemon
    _seed_pending(home, "prop-edit-1", mechanism="old mechanism", paper_title="old title")
    resp = _post(base, "/research/review/edit", {
        "proposal_id": "prop-edit-1",
        "fields": {
            "mechanism": "new, corrected mechanism",
            "paper_title": "new title",
            "one_sentence_compression": "a crisp one liner",
        },
    })
    data = json.loads(resp.read())
    assert data["edited_proposal_id"] == "prop-edit-1"
    assert data["proposal"]["mechanism"] == "new, corrected mechanism"
    # Still pending, and the edit is visible via /data
    after = json.loads(_get(base, "/research/review/data").read())
    edited = next(p for p in after["pending"] if p["proposal_id"] == "prop-edit-1")
    assert edited["mechanism"] == "new, corrected mechanism"
    assert edited["paper_title"] == "new title"
    assert edited["one_sentence_compression"] == "a crisp one liner"


def test_edit_clears_optional_field_when_blanked(daemon):
    base, home = daemon
    _seed_pending(home, "prop-edit-clear", verdict="useful")
    resp = _post(base, "/research/review/edit", {
        "proposal_id": "prop-edit-clear",
        "fields": {"verdict": ""},
    })
    data = json.loads(resp.read())
    assert data["proposal"]["verdict"] is None


def test_edit_preserves_provenance(daemon):
    base, home = daemon
    _seed_pending(home, "prop-edit-prov", source_id="keep-this-source")
    resp = _post(base, "/research/review/edit", {
        "proposal_id": "prop-edit-prov",
        "fields": {"mechanism": "edited"},
    })
    data = json.loads(resp.read())
    # Provenance + identity untouched.
    assert data["proposal"]["source_id"] == "keep-this-source"
    assert data["proposal"]["proposal_id"] == "prop-edit-prov"
    assert data["proposal"]["extraction_method"] == "fallback-heuristic"
    assert data["proposal"]["status"] == "pending"


def test_edit_rejects_empty_required_field(daemon):
    base, home = daemon
    _seed_pending(home, "prop-edit-empty")
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/review/edit", {
            "proposal_id": "prop-edit-empty",
            "fields": {"mechanism": "   "},
        })
    assert exc.value.code == 400


def test_edit_rejects_overlong_field(daemon):
    base, home = daemon
    _seed_pending(home, "prop-edit-long")
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/review/edit", {
            "proposal_id": "prop-edit-long",
            "fields": {"mechanism": "x" * 601},  # mechanism max_length=600
        })
    assert exc.value.code == 400


def test_edit_404_when_not_pending(daemon):
    base, _ = daemon
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/review/edit", {
            "proposal_id": "nope", "fields": {"mechanism": "x"},
        })
    assert exc.value.code == 404


def test_edit_requires_proposal_id_and_fields(daemon):
    base, home = daemon
    _seed_pending(home, "prop-edit-args")
    with pytest.raises(HTTPError) as exc:
        _post(base, "/research/review/edit", {"fields": {"mechanism": "x"}})
    assert exc.value.code == 400
    with pytest.raises(HTTPError) as exc2:
        _post(base, "/research/review/edit", {"proposal_id": "prop-edit-args"})
    assert exc2.value.code == 400


# ---------------------------------------------------------------------------
# Security regression — new routes inherit CORS hardening
# ---------------------------------------------------------------------------


def test_review_routes_reject_attacker_origin(daemon):
    base, home = daemon
    _seed_pending(home, "prop-cors-1")
    for path in (
        "/research/review/data",
        "/research/review/accept",
        "/research/review/reject",
        "/research/review/edit",
    ):
        req = Request(f"{base}{path}", data=b"{}", method="POST",
                      headers={"Content-Type": "application/json"})
        req.add_header("Origin", "http://attacker.com")
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 403, f"{path} should reject attacker origin"


def test_review_accept_rejects_cross_site_post(daemon):
    base, home = daemon
    _seed_pending(home, "prop-csrf-1")
    req = Request(
        f"{base}/research/review/accept",
        data=json.dumps({"proposal_id": "prop-csrf-1", "entity_mentions": []}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    req.add_header("Sec-Fetch-Site", "cross-site")
    with pytest.raises(HTTPError) as exc:
        urlopen(req, timeout=2)
    assert exc.value.code == 403
