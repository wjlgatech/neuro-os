"""
Tests for ``agent.research.gbrain_adapter``.

Strategy: drive the adapter against a deterministic fixture
(``tests/fixtures/research/gbrain_export.json``) so the tests are
hermetic — no live gbrain process required.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agent.research import GbrainEntity, GbrainQuerySpec, MechanismCardProposal
from agent.research.gbrain_adapter import (
    fetch_entities,
    fetch_from_export_file,
    ingest,
    translate,
)
from agent.research.proposals import list_proposals


FIXTURE = Path(__file__).parent / "fixtures" / "research" / "gbrain_export.json"


# ---------------------------------------------------------------------------
# translate() — unit tests for the conservative skip policy.
# ---------------------------------------------------------------------------


def _entity(**overrides) -> GbrainEntity:
    base = dict(
        slug="test-slug",
        title="Test entity",
        page_kind="claim",
        body_excerpt=(
            "When prices rise, customers leave. The mechanism is that "
            "switching cost determines retention. We predict that companies "
            "with high switching cost will retain customers during inflation. "
            "This breaks when a competitor offers free migration."
        ),
        typed_relationships=["causes:retention"],
        backlinks=3,
        confidence_hint="medium",
    )
    base.update(overrides)
    return GbrainEntity(**base)


def test_translate_accepts_well_shaped_claim():
    ent = _entity()
    prop = translate(ent, source_query="test")
    assert prop is not None
    assert isinstance(prop, MechanismCardProposal)
    assert prop.extraction_method == "gbrain-mcp"
    assert prop.confidence == "medium"
    assert prop.source_id == "gbrain:test-slug"
    assert prop.paper_source == "gbrain:test-slug"
    assert "switching cost" in prop.mechanism
    assert prop.proposal_id.startswith("gbrain-test-slug-")


def test_translate_skips_non_claim_pages():
    ent = _entity(page_kind="person")
    assert translate(ent, source_query="test") is None


def test_translate_skips_thin_excerpts():
    ent = _entity(body_excerpt="Markets go up.")
    assert translate(ent, source_query="test") is None


def test_translate_skips_descriptive_no_causal_verb():
    ent = _entity(
        body_excerpt=(
            "This is a description. It contains many words. It does not "
            "name any mechanism. It is purely descriptive prose with no "
            "causal structure or falsifiable prediction whatsoever today."
        ),
    )
    assert translate(ent, source_query="test") is None


def test_translate_defaults_confidence_to_low_when_no_hint():
    ent = _entity(confidence_hint=None)
    prop = translate(ent, source_query="test")
    assert prop is not None
    assert prop.confidence == "low"


def test_translate_picks_invariant_from_typed_relationships():
    ent = _entity(typed_relationships=["causes:retention", "mentions:foo"])
    prop = translate(ent, source_query="test")
    assert prop is not None
    assert prop.invariant.startswith("causes:")


def test_translate_falls_back_to_title_when_no_causal_relationship():
    ent = _entity(typed_relationships=["mentions:foo", "cites:bar"])
    prop = translate(ent, source_query="test")
    assert prop is not None
    assert prop.invariant.startswith("Subject:")


def test_translate_returns_frozen_proposal():
    ent = _entity()
    prop = translate(ent, source_query="test")
    assert prop is not None
    with pytest.raises(Exception):  # noqa: B017
        prop.status = "accepted"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# fetch_entities() — boundary validation.
# ---------------------------------------------------------------------------


def test_fetch_entities_validates_each_row():
    """A valid row produces a GbrainEntity; a malformed row is dropped."""
    spec = GbrainQuerySpec(query="test")

    def call_gbrain(_):
        return [
            {  # valid
                "slug": "good", "title": "Good entity",
                "page_kind": "claim", "body_excerpt": "x" * 120,
                "typed_relationships": [], "backlinks": 0,
            },
            {"slug": "bad"},  # missing required fields
        ]

    out = fetch_entities(spec, call_gbrain=call_gbrain)
    assert len(out) == 1
    assert out[0].slug == "good"


def test_fetch_from_export_file_respects_limit(tmp_path):
    spec = GbrainQuerySpec(query="anything", limit=2)
    fetch = fetch_from_export_file(FIXTURE)
    raw = fetch(spec)
    assert len(raw) == 2


def test_fetch_from_export_file_raises_on_non_list(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"not": "a list"}))
    fetch = fetch_from_export_file(bad)
    with pytest.raises(ValueError):
        fetch(GbrainQuerySpec(query="x"))


# ---------------------------------------------------------------------------
# ingest() — end-to-end from fixture to queue.
# ---------------------------------------------------------------------------


def test_ingest_against_fixture(tmp_path):
    """The shipped fixture has 5 entities; the conservative translator
    should accept exactly the 2 well-shaped claims (yang-pricing-power-2024
    and yang-compounding-2024) and skip the other 3."""
    home = tmp_path / "research"
    spec = GbrainQuerySpec(query="mechanism candidates", limit=10)
    run = ingest(
        spec=spec,
        call_gbrain=fetch_from_export_file(FIXTURE),
        home=home,
        now=datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    assert run.sources_scanned == 5
    assert run.proposals_emitted == 2
    assert run.extraction_method == "gbrain-mcp"
    assert run.cost_usd_estimate == 0.0  # zero-LLM in v0 adapter

    pending = list_proposals(home=home, status="pending")
    assert len(pending) == 2
    slugs = sorted(p.source_id for p in pending)
    assert slugs == [
        "gbrain:yang-compounding-2024",
        "gbrain:yang-pricing-power-2024",
    ]


def test_ingest_run_is_frozen(tmp_path):
    home = tmp_path / "research"
    spec = GbrainQuerySpec(query="test")
    run = ingest(
        spec=spec,
        call_gbrain=fetch_from_export_file(FIXTURE),
        home=home,
    )
    with pytest.raises(Exception):  # noqa: B017
        run.proposals_emitted = 999  # type: ignore[misc]


def test_ingest_cost_discipline(tmp_path):
    """Lane 1 invariant: the gbrain adapter must NOT call any LLM.
    Cost in the IngestionRun must be exactly 0.0 for the gbrain-mcp method."""
    home = tmp_path / "research"
    run = ingest(
        spec=GbrainQuerySpec(query="test"),
        call_gbrain=fetch_from_export_file(FIXTURE),
        home=home,
    )
    assert run.cost_usd_estimate == 0.0
