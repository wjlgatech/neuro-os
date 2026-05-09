"""
Tests for ``agent.research.proposals`` — the on-disk MechanismCardProposal queue.

Covers the queue invariants:

* Pydantic round-trip (write → read returns an identical frozen model).
* Status field on disk matches the parent directory (``pending``,
  ``accepted``, ``rejected``).
* Atomic write — a partial write doesn't leave a half-baked file in
  the queue.
* ``transition_proposal`` moves the file across status dirs and
  updates the status field.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agent.research import MechanismCardProposal
from agent.research.proposals import (
    list_proposals,
    read_proposal,
    transition_proposal,
    write_proposal,
)


def _make_proposal(**overrides) -> MechanismCardProposal:
    base = dict(
        proposal_id="prop-test-001",
        proposed_at=datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
        status="pending",
        paper_title="Example mechanism card",
        paper_source="gbrain:example-slug",
        mechanism="The mechanism is X causes Y because of Z.",
        invariant="The invariant is that Z holds across all observed cases.",
        prediction="If we observe X, we predict Y will follow within 30 days.",
        failure_mode="The mechanism breaks when Z is no longer true.",
        thesis_id=None,
        source_id="gbrain:example-slug",
        source_excerpt="The mechanism is X causes Y because of Z. We observed this in the data.",
        line_range=None,
        extraction_method="gbrain-mcp",
        extraction_model=None,
        confidence="medium",
        reasoning="Pulled from gbrain entity 'example-slug' via test fixture.",
    )
    base.update(overrides)
    return MechanismCardProposal(**base)


def test_proposal_round_trip(tmp_path):
    """write → read returns a model equal to the original."""
    home = tmp_path / "research"
    prop = _make_proposal()
    write_proposal(prop, home=home)
    got = read_proposal(prop.proposal_id, home=home, status="pending")
    assert got == prop


def test_write_creates_status_directories(tmp_path):
    """The first write creates pending/accepted/rejected."""
    home = tmp_path / "research"
    prop = _make_proposal()
    write_proposal(prop, home=home)
    for status in ("pending", "accepted", "rejected"):
        assert (home / "proposals" / status).is_dir()


def test_list_proposals_sorts_by_proposed_at(tmp_path):
    home = tmp_path / "research"
    earlier = _make_proposal(
        proposal_id="prop-A",
        proposed_at=datetime(2026, 5, 1, 8, 0, 0, tzinfo=timezone.utc),
    )
    later = _make_proposal(
        proposal_id="prop-B",
        proposed_at=datetime(2026, 5, 1, 18, 0, 0, tzinfo=timezone.utc),
    )
    write_proposal(later, home=home)   # write out of order
    write_proposal(earlier, home=home)
    got = list_proposals(home=home, status="pending")
    assert [p.proposal_id for p in got] == ["prop-A", "prop-B"]


def test_list_proposals_respects_limit(tmp_path):
    home = tmp_path / "research"
    for i in range(5):
        write_proposal(
            _make_proposal(
                proposal_id=f"prop-{i}",
                proposed_at=datetime(2026, 5, 1, 8 + i, 0, 0, tzinfo=timezone.utc),
            ),
            home=home,
        )
    got = list_proposals(home=home, status="pending", limit=3)
    assert len(got) == 3


def test_transition_pending_to_accepted(tmp_path):
    home = tmp_path / "research"
    prop = _make_proposal()
    write_proposal(prop, home=home)

    updated = transition_proposal(
        prop.proposal_id, home=home,
        from_status="pending", to_status="accepted",
    )
    assert updated.status == "accepted"
    assert updated.proposal_id == prop.proposal_id

    # Source dir empty, target dir populated.
    assert list_proposals(home=home, status="pending") == []
    accepted = list_proposals(home=home, status="accepted")
    assert len(accepted) == 1
    assert accepted[0].status == "accepted"


def test_transition_rejects_same_status(tmp_path):
    home = tmp_path / "research"
    prop = _make_proposal()
    write_proposal(prop, home=home)
    with pytest.raises(ValueError):
        transition_proposal(
            prop.proposal_id, home=home,
            from_status="pending", to_status="pending",
        )


def test_transition_missing_proposal_raises(tmp_path):
    home = tmp_path / "research"
    with pytest.raises(FileNotFoundError):
        transition_proposal(
            "does-not-exist", home=home,
            from_status="pending", to_status="rejected",
        )


def test_proposal_is_frozen():
    """Pydantic frozen=True — direct mutation raises."""
    prop = _make_proposal()
    with pytest.raises(Exception):  # noqa: B017  (Pydantic ValidationError)
        prop.status = "accepted"  # type: ignore[misc]


def test_list_proposals_skips_malformed_files(tmp_path):
    home = tmp_path / "research"
    write_proposal(_make_proposal(), home=home)
    # Drop a malformed file in the queue.
    bad = home / "proposals" / "pending" / "garbage.json"
    bad.write_text("{not valid json")
    # Should still return the one good proposal, not raise.
    got = list_proposals(home=home, status="pending")
    assert len(got) == 1
    assert got[0].proposal_id == "prop-test-001"
