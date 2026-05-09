"""
Tests for Lane 4 — entity propagation across verticals.

Covers:

* Entity round-trip (frozen Pydantic, store write/read).
* upsert_entity is append-only — multiple upserts of the same slug
  build a timeline; read_entity returns the LATEST visible row.
* Default-private: entities written by research are NOT visible to
  investment / startup / founder_loop unless explicitly shared.
* share_entity broadens visibility for ALL prior + future rows of the
  named slug; reads from other verticals start succeeding after the
  share event.
* MechanismCardProposal / MechanismCard now carry entity_mentions
  (default empty); the proposals queue round-trips them.
* CLI: ``research entity-list`` / ``research entity-read`` with
  ``--reader`` flag respects the visibility model.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from agent.cross_vertical import (
    Entity,
    list_entities,
    read_entity,
    share_entity,
    upsert_entity,
)
from agent.research import MechanismCard, MechanismCardProposal
from agent.research.proposals import read_proposal, write_proposal


NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Entity round-trip
# ---------------------------------------------------------------------------


def test_upsert_entity_writes_and_reads_back(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(
        slug="nvda",
        kind="company",
        title="NVIDIA Corp.",
        source_vertical="research",
        compiled_truth="GPU vendor with strong moat.",
        store=store,
        ts=NOW,
    )
    got = read_entity(slug="nvda", reader="research", store=store)
    assert got is not None
    assert got.slug == "nvda"
    assert got.kind == "company"
    assert got.title == "NVIDIA Corp."
    assert got.source_vertical == "research"
    assert got.compiled_truth == "GPU vendor with strong moat."


def test_entity_is_frozen():
    ent = Entity(
        id="abc",
        slug="x",
        kind="topic",
        title="X",
        source_vertical="research",
        compiled_truth="",
        ts=NOW,
        visible_to=["research"],
    )
    with pytest.raises(Exception):  # noqa: B017 (Pydantic ValidationError)
        ent.title = "Y"  # type: ignore[misc]


def test_read_entity_returns_none_when_missing(tmp_path):
    store = tmp_path / "cv.jsonl"
    assert read_entity(slug="ghost", reader="research", store=store) is None


def test_read_entity_returns_none_when_store_missing(tmp_path):
    store = tmp_path / "does-not-exist.jsonl"
    assert read_entity(slug="x", reader="research", store=store) is None


# ---------------------------------------------------------------------------
# Append-only timeline
# ---------------------------------------------------------------------------


def test_multiple_upserts_build_timeline_and_read_returns_latest(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(
        slug="nvda", kind="company", title="NVIDIA",
        source_vertical="research", compiled_truth="v1",
        store=store, ts=NOW - timedelta(days=2),
    )
    upsert_entity(
        slug="nvda", kind="company", title="NVIDIA Corp",
        source_vertical="research", compiled_truth="v2 (newer)",
        store=store, ts=NOW - timedelta(days=1),
    )
    upsert_entity(
        slug="nvda", kind="company", title="NVIDIA Corporation",
        source_vertical="research", compiled_truth="v3 (newest)",
        store=store, ts=NOW,
    )
    # Three rows on disk (append-only):
    rows = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
    entity_rows = [r for r in rows if r.get("row_kind") == "entity"]
    assert len(entity_rows) == 3
    # read_entity returns the LATEST visible:
    got = read_entity(slug="nvda", reader="research", store=store)
    assert got is not None
    assert got.compiled_truth == "v3 (newest)"
    assert got.title == "NVIDIA Corporation"


def test_list_entities_returns_one_per_slug_latest_first(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(
        slug="nvda", kind="company", title="NVIDIA",
        source_vertical="research",
        store=store, ts=NOW - timedelta(days=3),
    )
    upsert_entity(
        slug="moat", kind="topic", title="Moat theory",
        source_vertical="research",
        store=store, ts=NOW - timedelta(days=1),
    )
    upsert_entity(
        # Duplicate slug, should NOT show up twice — only latest.
        slug="nvda", kind="company", title="NVIDIA v2",
        source_vertical="research",
        store=store, ts=NOW,
    )
    out = list_entities(reader="research", store=store)
    assert len(out) == 2
    # Newest first.
    assert out[0].slug == "nvda"
    assert out[0].title == "NVIDIA v2"
    assert out[1].slug == "moat"


def test_list_entities_filter_by_kind(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(slug="nvda", kind="company", title="NVIDIA",
                  source_vertical="research", store=store, ts=NOW)
    upsert_entity(slug="moat", kind="topic", title="Moat",
                  source_vertical="research", store=store, ts=NOW)
    only_companies = list_entities(reader="research", kind="company", store=store)
    assert [e.slug for e in only_companies] == ["nvda"]


# ---------------------------------------------------------------------------
# Default-PRIVATE + share_entity broadening
# ---------------------------------------------------------------------------


def test_default_visibility_is_source_vertical_only(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(
        slug="secret-thesis", kind="topic", title="Secret",
        source_vertical="research", store=store, ts=NOW,
    )
    # Source can see it.
    assert read_entity(slug="secret-thesis", reader="research", store=store) is not None
    # Other verticals cannot.
    for reader in ("investment", "startup", "founder_loop"):
        got = read_entity(slug="secret-thesis", reader=reader, store=store)
        assert got is None, f"{reader} unexpectedly saw research's private entity"


def test_explicit_visible_to_at_upsert(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(
        slug="open-thesis", kind="topic", title="Open",
        source_vertical="research",
        visible_to=["research", "investment"],
        store=store, ts=NOW,
    )
    assert read_entity(slug="open-thesis", reader="research", store=store) is not None
    assert read_entity(slug="open-thesis", reader="investment", store=store) is not None
    # startup still locked out.
    assert read_entity(slug="open-thesis", reader="startup", store=store) is None


def test_share_entity_broadens_visibility(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(
        slug="nvda", kind="company", title="NVIDIA",
        source_vertical="research", store=store, ts=NOW,
    )
    # Before share: investment can't see.
    assert read_entity(slug="nvda", reader="investment", store=store) is None
    # Share → broaden to investment.
    share_entity(slug="nvda", add_visible=["investment"], store=store, ts=NOW)
    # After share: investment can see, startup still cannot.
    assert read_entity(slug="nvda", reader="investment", store=store) is not None
    assert read_entity(slug="nvda", reader="startup", store=store) is None


def test_share_entity_applies_to_all_prior_rows(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(
        slug="nvda", kind="company", title="NVIDIA v1",
        source_vertical="research",
        compiled_truth="version 1",
        store=store, ts=NOW - timedelta(days=2),
    )
    upsert_entity(
        slug="nvda", kind="company", title="NVIDIA v2",
        source_vertical="research",
        compiled_truth="version 2",
        store=store, ts=NOW - timedelta(days=1),
    )
    share_entity(slug="nvda", add_visible=["investment"], store=store, ts=NOW)
    # Investment now sees the LATEST (v2).
    got = read_entity(slug="nvda", reader="investment", store=store)
    assert got is not None
    assert got.title == "NVIDIA v2"


def test_share_entity_visible_to_all(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(
        slug="public", kind="topic", title="Public Thing",
        source_vertical="research", store=store, ts=NOW,
    )
    share_entity(slug="public", add_visible=["__all__"], store=store, ts=NOW)
    for reader in ("research", "investment", "startup", "founder_loop"):
        assert read_entity(slug="public", reader=reader, store=store) is not None


def test_list_entities_respects_visibility(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(slug="private", kind="topic", title="P",
                  source_vertical="research", store=store, ts=NOW)
    upsert_entity(slug="shared", kind="topic", title="S",
                  source_vertical="research",
                  visible_to=["research", "investment"],
                  store=store, ts=NOW)
    # Investment sees only the shared one.
    inv_view = list_entities(reader="investment", store=store)
    assert [e.slug for e in inv_view] == ["shared"]


# ---------------------------------------------------------------------------
# MechanismCardProposal / MechanismCard carry entity_mentions
# ---------------------------------------------------------------------------


def _make_proposal(**overrides) -> MechanismCardProposal:
    base = dict(
        proposal_id="prop-test-mentions",
        proposed_at=NOW,
        status="pending",
        paper_title="Test card",
        paper_source="gbrain:test",
        mechanism="X causes Y because Z.",
        invariant="Z holds.",
        prediction="If X, then Y in 30d.",
        failure_mode="When Z breaks.",
        thesis_id=None,
        source_id="gbrain:test",
        source_excerpt="X causes Y because Z. We see this in the data.",
        line_range=None,
        extraction_method="gbrain-mcp",
        extraction_model=None,
        confidence="medium",
        reasoning="From a test fixture.",
        entity_mentions=["nvda", "moat-theory"],
    )
    base.update(overrides)
    return MechanismCardProposal(**base)


def test_proposal_round_trips_entity_mentions(tmp_path):
    home = tmp_path / "research"
    prop = _make_proposal()
    write_proposal(prop, home=home)
    got = read_proposal(prop.proposal_id, home=home, status="pending")
    assert got.entity_mentions == ["nvda", "moat-theory"]


def test_mechanism_card_carries_entity_mentions():
    card = MechanismCard(
        id="card-1",
        ts=NOW,
        paper_title="t",
        paper_source="s",
        mechanism="m" * 30,
        invariant="i" * 30,
        prediction="p" * 30,
        failure_mode="f" * 30,
        thesis_id=None,
        entity_mentions=["nvda", "ai-safety"],
    )
    assert card.entity_mentions == ["nvda", "ai-safety"]


def test_mechanism_card_default_entity_mentions_is_empty():
    card = MechanismCard(
        id="card-1",
        ts=NOW,
        paper_title="t",
        paper_source="s",
        mechanism="m" * 30,
        invariant="i" * 30,
        prediction="p" * 30,
        failure_mode="f" * 30,
    )
    assert card.entity_mentions == []


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


def _run(*args: str, env_overrides: dict | None = None) -> tuple[int, str, str]:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    p = subprocess.run(
        [sys.executable, "-m", "agent", *args],
        capture_output=True, text=True, timeout=30,
        env=env,
    )
    return p.returncode, p.stdout, p.stderr


def test_cli_entity_list_empty(tmp_path):
    store = tmp_path / "cv.jsonl"
    rc, out, err = _run("research", "entity-list", "--store", str(store))
    assert rc == 0, err
    assert json.loads(out) == []


def test_cli_entity_list_returns_research_entities(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(slug="nvda", kind="company", title="NVIDIA",
                  source_vertical="research", store=store, ts=NOW)
    upsert_entity(slug="moat", kind="topic", title="Moat",
                  source_vertical="research", store=store, ts=NOW)
    rc, out, err = _run("research", "entity-list", "--store", str(store))
    assert rc == 0, err
    parsed = json.loads(out)
    slugs = sorted(e["slug"] for e in parsed)
    assert slugs == ["moat", "nvda"]


def test_cli_entity_list_respects_reader_visibility(tmp_path):
    store = tmp_path / "cv.jsonl"
    # Research-private.
    upsert_entity(slug="private", kind="topic", title="P",
                  source_vertical="research", store=store, ts=NOW)
    # Reading as investment → empty.
    rc, out, _ = _run(
        "research", "entity-list",
        "--store", str(store), "--reader", "investment",
    )
    assert rc == 0
    assert json.loads(out) == []


def test_cli_entity_read_returns_entity(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(slug="nvda", kind="company", title="NVIDIA",
                  source_vertical="research",
                  compiled_truth="GPU vendor",
                  store=store, ts=NOW)
    rc, out, err = _run(
        "research", "entity-read",
        "--slug", "nvda", "--store", str(store),
    )
    assert rc == 0, err
    parsed = json.loads(out)
    assert parsed["slug"] == "nvda"
    assert parsed["compiled_truth"] == "GPU vendor"


def test_cli_entity_read_missing_slug(tmp_path):
    store = tmp_path / "cv.jsonl"
    rc, out, _ = _run(
        "research", "entity-read",
        "--slug", "ghost", "--store", str(store),
    )
    assert rc == 0
    assert "no entity 'ghost'" in out


def test_cli_entity_read_blocks_non_visible(tmp_path):
    store = tmp_path / "cv.jsonl"
    upsert_entity(slug="private", kind="topic", title="P",
                  source_vertical="research", store=store, ts=NOW)
    rc, out, _ = _run(
        "research", "entity-read",
        "--slug", "private", "--store", str(store),
        "--reader", "investment",
    )
    assert rc == 0
    assert "no entity 'private' visible to 'investment'" in out


# ---------------------------------------------------------------------------
# Backwards compat: existing notes / proposals without entity_mentions still load
# ---------------------------------------------------------------------------


def test_old_proposal_without_entity_mentions_still_loads(tmp_path):
    """Manual write of a JSON missing the entity_mentions key — Pydantic
    should default it to []. (Backwards-compat check.)"""
    home = tmp_path / "research"
    pending_dir = home / "proposals" / "pending"
    pending_dir.mkdir(parents=True)
    body = {
        "proposal_id": "legacy-prop",
        "proposed_at": NOW.isoformat(),
        "status": "pending",
        "paper_title": "Legacy",
        "paper_source": "gbrain:legacy",
        "mechanism": "m" * 50,
        "invariant": "i" * 30,
        "prediction": "p" * 30,
        "failure_mode": "f" * 30,
        "source_id": "gbrain:legacy",
        "source_excerpt": "x" * 100,
        "extraction_method": "gbrain-mcp",
        "confidence": "low",
        "reasoning": "no entity mentions in this row",
        # NO entity_mentions field at all.
    }
    (pending_dir / "legacy-prop.json").write_text(json.dumps(body))
    got = read_proposal("legacy-prop", home=home, status="pending")
    assert got.entity_mentions == []
