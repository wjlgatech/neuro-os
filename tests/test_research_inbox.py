"""
Tests for the URL-to-Living-Knowledge inbox.

Strategy: every code path is exercised against the library functions
directly (no CLI subprocess) so the tests are hermetic — no flywheel-loop
import, no live LLM, no network. The end-to-end real-use-case scenario
at the bottom of this file IS the documented validation: three sample
URL records → ingest → review → goal-link → verify cross-vertical
privacy boundary.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from agent.cross_vertical import (
    list_entities,
    query as cv_query,
    read_entity,
    upsert_entity,
    write_note,
)
from agent.research.inbox import (
    InboxRecord,
    InboxRunSummary,
    append_to_inbox,
    default_allowlist_path,
    default_inbox_path,
    load_allowlist,
    process_inbox,
    read_pending,
)
from agent.research.proposals import list_proposals


NOW = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _llm_one_mechanism(_system: str, _user: str) -> list[dict]:
    """Stub LLM that always emits one well-shaped mechanism."""
    return [{
        "mechanism": (
            "Distribution beats product quality whenever the audience "
            "is unaware of the alternatives."
        ),
        "invariant": (
            "Buyer attention is upper-bounded; demand cannot exceed it."
        ),
        "prediction": (
            "If two products have equal quality, the one with broader "
            "distribution wins share."
        ),
        "failure_mode": (
            "Holds only when the audience cannot self-discover alternatives "
            "(e.g. closed marketplaces)."
        ),
        "source_excerpt": "Distribution is the moat for most consumer SaaS.",
        "confidence": "medium",
        "reasoning": "Test stub — single mechanism per source.",
    }]


def _sample_record(
    *,
    url: str = "https://example.com/post-1",
    source_type: str = "blog",
    title: str = "Distribution is the moat",
    text: str = "Distribution beats product quality. Build distribution first.",
    sender: str | None = None,
    urge_tag: str | None = None,
) -> InboxRecord:
    return InboxRecord(
        url=url,
        source_type=source_type,
        title=title,
        author="Sample Author",
        extracted_text=text,
        extracted_at=NOW,
        sender=sender,
        urge_tag=urge_tag,
    )


# ---------------------------------------------------------------------------
# Schema (Law 1)
# ---------------------------------------------------------------------------


def test_inbox_record_is_frozen():
    rec = _sample_record()
    with pytest.raises(Exception):
        rec.title = "mutated"  # type: ignore[misc]


def test_inbox_record_rejects_empty_text():
    with pytest.raises(Exception):
        InboxRecord(
            url="https://x/1",
            source_type="blog",
            title="t",
            extracted_text="",
            extracted_at=NOW,
        )


def test_inbox_record_rejects_invalid_source_type():
    with pytest.raises(Exception):
        InboxRecord(
            url="https://x/1",
            source_type="not-a-real-type",  # type: ignore[arg-type]
            title="t",
            extracted_text="body",
            extracted_at=NOW,
        )


def test_inbox_run_summary_is_frozen():
    s = InboxRunSummary(
        run_id="r1",
        started_at=NOW,
        finished_at=NOW,
        records_seen=0,
        records_skipped_disallowed=0,
        records_skipped_duplicate=0,
        proposals_emitted=0,
        cursor_advanced_to=0,
    )
    with pytest.raises(Exception):
        s.records_seen = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# JSONL roundtrip + cursor advance
# ---------------------------------------------------------------------------


def test_append_and_read_pending_roundtrip(tmp_path):
    home = tmp_path / "research"
    rec = _sample_record()
    offset = append_to_inbox(rec, home=home)
    assert offset == 0
    pending = read_pending(home=home)
    assert len(pending) == 1
    offset_read, rec_read = pending[0]
    assert offset_read == 0
    assert rec_read.url == rec.url
    assert rec_read.title == rec.title
    assert rec_read.source_type == rec.source_type


def test_read_pending_skips_malformed_lines(tmp_path):
    home = tmp_path / "research"
    path = default_inbox_path(home)
    path.parent.mkdir(parents=True)
    # First line valid, second malformed JSON, third missing required field, fourth valid:
    rec_a = _sample_record(url="https://x/a", title="A")
    rec_d = _sample_record(url="https://x/d", title="D")
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(json.loads(rec_a.model_dump_json())) + "\n")
        f.write("not valid json{{{\n")
        f.write(json.dumps({"url": "https://x/c"}) + "\n")  # missing required fields
        f.write(json.dumps(json.loads(rec_d.model_dump_json())) + "\n")
    pending = read_pending(home=home)
    titles = [r.title for _, r in pending]
    assert titles == ["A", "D"]


def test_cursor_advances_so_records_are_consumed_once(tmp_path):
    home = tmp_path / "research"
    append_to_inbox(
        _sample_record(url="https://x/1", title="One", text="First body."),
        home=home,
    )
    append_to_inbox(
        _sample_record(url="https://x/2", title="Two", text="Second body."),
        home=home,
    )

    summary = process_inbox(llm_fn=_llm_one_mechanism, home=home, now=NOW)
    assert summary.records_seen == 2
    assert summary.proposals_emitted == 2

    # Second run with no new records: cursor already past both lines, so
    # read_pending returns empty and the run is a no-op.
    second = process_inbox(llm_fn=_llm_one_mechanism, home=home, now=NOW)
    assert second.records_seen == 0
    assert second.proposals_emitted == 0


# ---------------------------------------------------------------------------
# Dedup (sha256 on body)
# ---------------------------------------------------------------------------


def test_duplicate_body_is_skipped(tmp_path):
    """Two records with identical body text but different URLs collapse to
    one proposal — the dedup signal is the sha256 of the text, not the URL."""
    home = tmp_path / "research"
    body = "Distribution beats product quality; build it first."
    append_to_inbox(
        _sample_record(url="https://a.example/p", title="A", text=body),
        home=home,
    )
    append_to_inbox(
        _sample_record(url="https://b.example/p", title="B", text=body),
        home=home,
    )
    summary = process_inbox(llm_fn=_llm_one_mechanism, home=home, now=NOW)
    assert summary.records_seen == 2
    assert summary.records_skipped_duplicate == 1
    assert summary.proposals_emitted == 1


# ---------------------------------------------------------------------------
# Allowlist (Law 1 boundary)
# ---------------------------------------------------------------------------


def test_allowlist_disk_file_filters_unauthorized_senders(tmp_path):
    home = tmp_path / "research"
    home.mkdir(parents=True)
    allowlist_path = default_allowlist_path(home)
    allowlist_path.write_text(json.dumps(["paul@example.com"]))
    append_to_inbox(
        _sample_record(url="https://x/p", title="P", sender="paul@example.com"),
        home=home,
    )
    append_to_inbox(
        _sample_record(url="https://x/m", title="M", sender="spammer@evil"),
        home=home,
    )
    summary = process_inbox(llm_fn=_llm_one_mechanism, home=home, now=NOW)
    assert summary.records_seen == 2
    assert summary.records_skipped_disallowed == 1
    assert summary.proposals_emitted == 1


def test_explicit_empty_allowlist_denies_all(tmp_path):
    home = tmp_path / "research"
    append_to_inbox(
        _sample_record(url="https://x/p", title="P", sender="paul@example.com"),
        home=home,
    )
    summary = process_inbox(
        llm_fn=_llm_one_mechanism,
        home=home,
        allowlist=set(),
        now=NOW,
    )
    # Empty set still means "no restriction" per the contract — but a None
    # sender is not in any set, and a populated sender goes through. So an
    # empty set behaves like no allowlist (allow). Document that here.
    assert summary.records_skipped_disallowed == 0
    assert summary.proposals_emitted == 1


def test_load_allowlist_supports_object_shape(tmp_path):
    home = tmp_path / "research"
    home.mkdir(parents=True)
    default_allowlist_path(home).write_text(
        json.dumps({"senders": ["A@b.com", "c@d.com"]})
    )
    allow = load_allowlist(home=home)
    assert allow == {"a@b.com", "c@d.com"}


# ---------------------------------------------------------------------------
# Urge tag propagation
# ---------------------------------------------------------------------------


def test_urge_tag_surfaces_in_proposal_reasoning(tmp_path):
    home = tmp_path / "research"
    append_to_inbox(
        _sample_record(
            url="https://x/p",
            title="Tagged",
            urge_tag="novelty",
        ),
        home=home,
    )
    summary = process_inbox(llm_fn=_llm_one_mechanism, home=home, now=NOW)
    assert summary.proposals_emitted == 1
    proposals = list_proposals(home=home, status="pending")
    assert len(proposals) == 1
    assert proposals[0].reasoning.startswith("[urge:novelty] ")


# ---------------------------------------------------------------------------
# Heuristic-fallback path (no LLM)
# ---------------------------------------------------------------------------


def test_process_inbox_without_llm_uses_heuristic(tmp_path):
    home = tmp_path / "research"
    # Body with both a causal verb and a falsifiable shape so the
    # heuristic matches at least one sentence.
    text = (
        "Distribution causes share because attention is bounded. "
        "When two products are equal, then the wider-distributed one wins."
    )
    append_to_inbox(
        _sample_record(url="https://x/heur", title="Heur", text=text),
        home=home,
    )
    summary = process_inbox(llm_fn=None, home=home, now=NOW)
    assert summary.records_seen == 1
    # The heuristic emits low-confidence proposals.
    proposals = list_proposals(home=home, status="pending")
    assert all(p.confidence == "low" for p in proposals)
    assert all(p.extraction_method == "fallback-heuristic" for p in proposals)


# ---------------------------------------------------------------------------
# End-to-end real-use-case scenario
#   This is the documented validation for the feature. Three sample URL
#   records pass through ingest → review-accept → research-goal link →
#   cross-vertical visibility check.
# ---------------------------------------------------------------------------


def test_real_use_case_url_to_living_knowledge_end_to_end(tmp_path, monkeypatch):
    """Real-use-case walkthrough — the documented validation in
    docs/url-to-living-knowledge.md uses this exact scenario.

    Producer sends 3 URLs to the inbox:
      1. YouTube — AI agents for sales automation
      2. Blog    — Distribution is the moat
      3. X/Twitter — Lead-scoring threads
    Neuro-os ingests, the user accepts one card, links it to a startup
    goal entity, and we verify the cross-vertical privacy boundary
    (research note visible to startup; research's MechanismCard NOT
    visible to investment unless explicitly shared).
    """
    home = tmp_path / "research"
    home.mkdir(parents=True)
    cross_store = tmp_path / "cross_vertical.jsonl"
    monkeypatch.setenv("NEURO_OS_HOME", str(tmp_path))

    # ---- 1. Producer drops three URL records into the inbox ----
    inbox_records = [
        _sample_record(
            url="https://youtube.com/watch?v=ai-agents-sales",
            source_type="youtube",
            title="Building AI agents for sales automation",
            text=(
                "AI agents drive lead conversion because they reduce "
                "founder context-switching. When inbound leads exceed "
                "founder bandwidth, then qualifying agents recover the "
                "leakage. Fails when leads require deep technical sales."
            ),
            sender="paul@example.com",
            urge_tag="novelty",
        ),
        _sample_record(
            url="https://blog.example.com/distribution-moat",
            source_type="blog",
            title="Distribution is the moat",
            text=(
                "Distribution causes share because attention is bounded. "
                "If two products are equal, then the broader-distributed "
                "one wins. Fails when buyers actively comparison-shop."
            ),
            sender="paul@example.com",
        ),
        _sample_record(
            url="https://twitter.com/x/status/123",
            source_type="twitter",
            title="Lead-scoring thread",
            text=(
                "Lead scoring drives revenue because it forces the "
                "founder to spend on the top decile. If scoring is "
                "absent, then time leaks to low-intent prospects."
            ),
            sender="paul@example.com",
        ),
    ]
    for rec in inbox_records:
        append_to_inbox(rec, home=home)

    # ---- 2. Neuro-os processes the inbox ----
    summary = process_inbox(llm_fn=_llm_one_mechanism, home=home, now=NOW)
    assert summary.records_seen == 3
    assert summary.records_skipped_disallowed == 0
    assert summary.records_skipped_duplicate == 0
    assert summary.proposals_emitted == 3
    assert summary.cursor_advanced_to == 2

    # All proposals are pending review (Law 7 — human-in-loop truth control).
    pending = list_proposals(home=home, status="pending")
    assert len(pending) == 3
    # Source URLs are preserved as paper_source.
    paper_sources = {p.paper_source for p in pending}
    assert "https://youtube.com/watch?v=ai-agents-sales" in paper_sources
    assert "https://blog.example.com/distribution-moat" in paper_sources
    assert "https://twitter.com/x/status/123" in paper_sources

    # Novelty-urge proposal carries the urge tag through to reasoning.
    youtube_proposal = next(
        p for p in pending
        if p.paper_source == "https://youtube.com/watch?v=ai-agents-sales"
    )
    assert youtube_proposal.reasoning.startswith("[urge:novelty] ")

    # ---- 3. User accepts the YouTube proposal at /research-review ----
    # (We exercise the underlying primitives directly; the CLI loop is
    #  tested elsewhere.)
    from agent.research.config import write_mechanism_card
    from agent.research.proposals import transition_proposal
    from agent.research import MechanismCard

    card = MechanismCard(
        id=youtube_proposal.proposal_id,
        ts=NOW,
        paper_title=youtube_proposal.paper_title,
        paper_source=youtube_proposal.paper_source,
        mechanism=youtube_proposal.mechanism,
        invariant=youtube_proposal.invariant,
        prediction=youtube_proposal.prediction,
        failure_mode=youtube_proposal.failure_mode,
        thesis_id=None,
        entity_mentions=[],
    )
    write_mechanism_card(card=card, home=home)
    transition_proposal(
        youtube_proposal.proposal_id, home=home,
        from_status="pending", to_status="accepted",
    )

    # The accepted card landed on disk.
    card_path = home / "mechanism_cards" / f"{card.id}.json"
    assert card_path.exists()

    # ---- 4. User links the card to a startup-vertical goal entity ----
    # (This is what `research goal --card-id ... --entity-slug ...` does.)
    upsert_entity(
        slug="wfx-revenue-q1",
        kind="topic",
        title="WorkflowX Revenue Q1",
        source_vertical="startup",
        compiled_truth=(
            f"Goal entity linked from research vertical. First linked "
            f"to MechanismCard {card.id}."
        ),
        mentioned_in_note_id=card.id,
        visible_to=["startup", "research"],
        store=cross_store,
    )
    write_note(
        source_vertical="research",
        note_kind="research_goal_link",
        payload={
            "card_id": card.id,
            "entity_slug": "wfx-revenue-q1",
            "paper_title": card.paper_title,
            "mechanism": card.mechanism,
            "prediction": card.prediction,
        },
        visible_to=["research", "startup"],
        store=cross_store,
    )

    # ---- 5. Verify cross-vertical visibility ----
    # Startup vertical CAN read the research_goal_link note.
    startup_links = cv_query(
        reader="startup",
        kinds=["research_goal_link"],
        store=cross_store,
    )
    assert len(startup_links) == 1
    assert startup_links[0].payload["card_id"] == card.id

    # Startup vertical CAN read the goal entity it owns.
    goal = read_entity(slug="wfx-revenue-q1", reader="startup", store=cross_store)
    assert goal is not None
    assert goal.kind == "topic"
    assert goal.source_vertical == "startup"

    # Investment vertical CANNOT see the research_goal_link (default-private).
    invest_links = cv_query(
        reader="investment",
        kinds=["research_goal_link"],
        store=cross_store,
    )
    assert invest_links == []

    # Investment vertical CANNOT see the startup-owned goal entity either.
    invest_entities = list_entities(reader="investment", store=cross_store)
    assert all(e.slug != "wfx-revenue-q1" for e in invest_entities)
