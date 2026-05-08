"""
Tests for the agent/cross_vertical.py interface.

Critical invariants (Phase 0 design decisions):
* Default visibility is PRIVATE (visible_to == [source_vertical]).
* `share_note` broadens visibility via append-only event (no mutation).
* `query` enforces visibility AFTER all other filters.
* `is_visible_to(source_vertical)` always True (you can read your own).
* `__all__` in visible_to broadens to every vertical.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agent.cross_vertical import (
    VerticalNote,
    query,
    share_note,
    write_note,
)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "cross_vertical.jsonl"


# ---------------------------------------------------------------------------
# Default visibility — PRIVATE
# ---------------------------------------------------------------------------


def test_default_visibility_is_private_to_source(store):
    """A note written without explicit visible_to is private to its source."""
    note = write_note(
        source_vertical="investment",
        note_kind="position_thesis",
        payload={"ticker": "ACME", "thesis": "secular growth"},
        store=store,
    )
    assert note.visible_to == ["investment"]


def test_research_cannot_read_investments_private_note(store):
    """Default-private means cross-vertical reads return empty."""
    write_note(
        source_vertical="investment",
        note_kind="position_thesis",
        payload={"ticker": "ACME"},
        store=store,
    )
    research_view = query(reader="research", store=store)
    assert research_view == []


def test_investment_can_always_read_its_own_notes(store):
    """The source vertical always sees its own notes regardless of visible_to."""
    write_note(
        source_vertical="investment",
        note_kind="position_thesis",
        payload={"ticker": "ACME"},
        store=store,
    )
    own_view = query(reader="investment", store=store)
    assert len(own_view) == 1
    assert own_view[0].source_vertical == "investment"


# ---------------------------------------------------------------------------
# Explicit cross-share via visible_to
# ---------------------------------------------------------------------------


def test_explicit_visible_to_lets_other_vertical_read(store):
    """Setting visible_to=['research'] at write-time lets research read."""
    write_note(
        source_vertical="investment",
        note_kind="position_thesis",
        payload={"ticker": "ACME"},
        visible_to=["investment", "research"],
        store=store,
    )
    research_view = query(reader="research", store=store)
    assert len(research_view) == 1


def test_all_visibility_broadcasts(store):
    """visible_to=['__all__'] makes the note visible to every vertical."""
    write_note(
        source_vertical="research",
        note_kind="mechanism_card",
        payload={"mechanism": "predictive coding"},
        visible_to=["__all__"],
        store=store,
    )
    for reader in ("founder_loop", "investment", "startup"):
        view = query(reader=reader, store=store)  # type: ignore[arg-type]
        assert len(view) == 1, f"reader={reader} could not see __all__ note"


# ---------------------------------------------------------------------------
# share_note (broaden after the fact)
# ---------------------------------------------------------------------------


def test_share_note_broadens_visibility_via_append_only_event(store):
    """share_note adds to visible_to without mutating the original row."""
    note = write_note(
        source_vertical="investment",
        note_kind="position_thesis",
        payload={"ticker": "ACME"},
        store=store,
    )
    # Before: research can't see it.
    assert query(reader="research", store=store) == []

    # Share with research.
    share_note(note_id=note.id, add_visible=["research"], store=store)

    # After: research sees it.
    research_view = query(reader="research", store=store)
    assert len(research_view) == 1
    assert "research" in research_view[0].visible_to
    # And startup still cannot.
    assert query(reader="startup", store=store) == []


def test_share_note_does_not_mutate_original_row(store):
    """The original note row should still show its original visible_to.
    The query layer folds share events on top."""
    write_note(
        source_vertical="investment",
        note_kind="position_thesis",
        payload={"ticker": "ACME"},
        store=store,
    )
    before_lines = store.read_text().splitlines()
    share_note(
        note_id=query(reader="investment", store=store)[0].id,
        add_visible=["research"],
        store=store,
    )
    after_lines = store.read_text().splitlines()
    # Original note line is unchanged (still 1 'kind: note' row).
    note_rows = [line for line in after_lines if '"kind": "note"' in line]
    note_rows_before = [line for line in before_lines if '"kind": "note"' in line]
    assert note_rows == note_rows_before


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_query_filters_by_kind(store):
    write_note(
        source_vertical="research",
        note_kind="mechanism_card",
        payload={"x": 1},
        visible_to=["__all__"],
        store=store,
    )
    write_note(
        source_vertical="research",
        note_kind="prediction_log",
        payload={"y": 2},
        visible_to=["__all__"],
        store=store,
    )
    only_cards = query(
        reader="investment", kinds=["mechanism_card"], store=store,
    )
    assert len(only_cards) == 1
    assert only_cards[0].note_kind == "mechanism_card"


def test_query_filters_by_source(store):
    write_note(
        source_vertical="research",
        note_kind="x",
        payload={},
        visible_to=["__all__"],
        store=store,
    )
    write_note(
        source_vertical="startup",
        note_kind="x",
        payload={},
        visible_to=["__all__"],
        store=store,
    )
    only_research = query(
        reader="investment", sources=["research"], store=store,
    )
    assert len(only_research) == 1
    assert only_research[0].source_vertical == "research"


def test_query_filters_by_since(store):
    now = datetime.now(timezone.utc)
    write_note(
        source_vertical="research",
        note_kind="x",
        payload={},
        ts=now - timedelta(days=2),
        visible_to=["__all__"],
        store=store,
    )
    write_note(
        source_vertical="research",
        note_kind="x",
        payload={},
        ts=now,
        visible_to=["__all__"],
        store=store,
    )
    recent = query(
        reader="investment",
        since=now - timedelta(hours=1),
        store=store,
    )
    assert len(recent) == 1


# ---------------------------------------------------------------------------
# VerticalNote frozen
# ---------------------------------------------------------------------------


def test_vertical_note_is_frozen(store):
    note = write_note(
        source_vertical="research",
        note_kind="x",
        payload={"a": 1},
        store=store,
    )
    with pytest.raises(Exception):
        note.payload = {"b": 2}  # type: ignore[misc]


def test_is_visible_to_helper(store):
    note = VerticalNote(
        id="abc",
        source_vertical="investment",
        note_kind="x",
        payload={},
        ts=datetime.now(timezone.utc),
        visible_to=["investment", "research"],
    )
    assert note.is_visible_to("investment") is True
    assert note.is_visible_to("research") is True
    assert note.is_visible_to("startup") is False
    assert note.is_visible_to("founder_loop") is False
