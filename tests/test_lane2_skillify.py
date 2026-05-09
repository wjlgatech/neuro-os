"""
Tests for Lane 2 — skillify (override-events → SkillProposals).

Covers:

* OverrideEvent round-trip (frozen Pydantic, append-only events.jsonl).
* read_override_events filters by vertical / drift_mode / since.
* extract_pattern groups by (vertical, drift_mode), threshold-gates,
  picks most-frequent user_action with recency tie-break.
* SkillProposal queue mirrors research/proposals shape (atomic write,
  status-dir invariant, transition).
* run_extraction skips already-proposed buckets unless told otherwise.
* CLI: log-override → extract → proposals → review (accept + reject).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from agent.skillify import (
    DEFAULT_THRESHOLD,
    OverrideEvent,
    SkillProposal,
    extract_pattern,
    list_skill_proposals,
    read_override_events,
    read_skill_proposal,
    run_extraction,
    transition_skill_proposal,
    write_override_event,
    write_skill_proposal,
)


NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# OverrideEvent round-trip + filters
# ---------------------------------------------------------------------------


def test_write_event_creates_jsonl_and_reads_back(tmp_path):
    home = tmp_path / "skill"
    ev = write_override_event(
        vertical="research",
        drift_mode="paper_collector",
        user_action="extracted into a Markdown brief",
        suggested_action="extract one mechanism card",
        notes="Markdown briefs feel lighter than the card template.",
        home=home,
        ts=NOW,
    )
    assert ev.event_id
    rows = read_override_events(home=home)
    assert len(rows) == 1
    assert rows[0] == ev


def test_event_is_frozen():
    ev = OverrideEvent(
        event_id="abc",
        ts=NOW,
        vertical="research",
        drift_mode="paper_collector",
        user_action="x",
    )
    with pytest.raises(Exception):  # noqa: B017
        ev.user_action = "y"  # type: ignore[misc]


def test_read_override_events_empty_home(tmp_path):
    home = tmp_path / "fresh"
    assert read_override_events(home=home) == []


def test_read_override_events_filter_by_vertical(tmp_path):
    home = tmp_path / "skill"
    write_override_event(vertical="research", drift_mode="x",
                         user_action="r1", home=home, ts=NOW)
    write_override_event(vertical="investment", drift_mode="x",
                         user_action="i1", home=home, ts=NOW)
    research_rows = read_override_events(home=home, vertical="research")
    assert len(research_rows) == 1
    assert research_rows[0].vertical == "research"


def test_read_override_events_filter_by_drift_mode(tmp_path):
    home = tmp_path / "skill"
    write_override_event(vertical="research", drift_mode="paper_collector",
                         user_action="r1", home=home, ts=NOW)
    write_override_event(vertical="research", drift_mode="topic_hopper",
                         user_action="r2", home=home, ts=NOW)
    rows = read_override_events(home=home, drift_mode="paper_collector")
    assert [r.user_action for r in rows] == ["r1"]


def test_read_override_events_filter_by_since(tmp_path):
    home = tmp_path / "skill"
    write_override_event(vertical="research", drift_mode="x",
                         user_action="old", home=home,
                         ts=NOW - timedelta(days=40))
    write_override_event(vertical="research", drift_mode="x",
                         user_action="recent", home=home,
                         ts=NOW - timedelta(days=5))
    rows = read_override_events(home=home, since=NOW - timedelta(days=10))
    assert [r.user_action for r in rows] == ["recent"]


def test_read_override_events_skips_malformed(tmp_path):
    home = tmp_path / "skill"
    write_override_event(vertical="research", drift_mode="x",
                         user_action="ok", home=home, ts=NOW)
    # Append a malformed line directly.
    (home / "events.jsonl").open("a").write("{not valid json\n")
    rows = read_override_events(home=home)
    assert len(rows) == 1


def test_event_atomic_write_does_not_corrupt_log(tmp_path):
    """Multiple writes produce N valid JSON lines, no partials."""
    home = tmp_path / "skill"
    for i in range(20):
        write_override_event(
            vertical="research", drift_mode="paper_collector",
            user_action=f"action-{i}", home=home,
            ts=NOW + timedelta(seconds=i),
        )
    text = (home / "events.jsonl").read_text()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 20
    for line in lines:
        json.loads(line)  # raises if any line is malformed


# ---------------------------------------------------------------------------
# extract_pattern — pure function
# ---------------------------------------------------------------------------


def _make_event(
    *, vertical="research", drift_mode="paper_collector",
    user_action="alt", offset_days=0, suggested=None,
) -> OverrideEvent:
    return OverrideEvent(
        event_id=f"ev-{vertical}-{drift_mode}-{offset_days}-{user_action[:6]}",
        ts=NOW - timedelta(days=offset_days),
        vertical=vertical,
        drift_mode=drift_mode,
        user_action=user_action,
        suggested_action=suggested,
    )


def test_extract_below_threshold_returns_nothing():
    events = [_make_event(user_action="alt") for _ in range(4)]
    out = extract_pattern(events, threshold=5)
    assert out == []


def test_extract_at_threshold_returns_one_proposal():
    events = [_make_event(user_action="alt") for _ in range(5)]
    out = extract_pattern(events, threshold=5)
    assert len(out) == 1
    p = out[0]
    assert p.vertical == "research"
    assert p.drift_mode == "paper_collector"
    assert p.candidate_action == "alt"
    assert p.based_on_event_count == 5


def test_extract_groups_by_vertical_drift_mode():
    events = [
        _make_event(vertical="research", drift_mode="paper_collector",
                    user_action="r-pc"),
    ] * 5 + [
        _make_event(vertical="research", drift_mode="topic_hopper",
                    user_action="r-th"),
    ] * 5 + [
        _make_event(vertical="investment", drift_mode="emotional",
                    user_action="i-em"),
    ] * 5
    out = extract_pattern(events, threshold=5)
    assert len(out) == 3
    keys = sorted((p.vertical, p.drift_mode) for p in out)
    assert keys == [
        ("investment", "emotional"),
        ("research", "paper_collector"),
        ("research", "topic_hopper"),
    ]


def test_extract_picks_most_frequent_user_action():
    events = []
    # 4 of "popular" + 2 of "rare" → "popular" wins.
    for i in range(4):
        events.append(_make_event(user_action="popular", offset_days=i))
    for i in range(2):
        events.append(_make_event(user_action="rare", offset_days=i + 10))
    # Total 6 ≥ threshold 5.
    out = extract_pattern(events, threshold=5)
    assert len(out) == 1
    assert out[0].candidate_action == "popular"


def test_extract_recency_breaks_ties():
    """When two user_actions tie on count, the most-recent wins."""
    events = [
        _make_event(user_action="A", offset_days=10),
        _make_event(user_action="A", offset_days=8),
        _make_event(user_action="B", offset_days=2),
        _make_event(user_action="B", offset_days=1),
        _make_event(user_action="C", offset_days=12),
    ]
    # A: 2, B: 2, C: 1 → tie A vs B; B is more recent → wins.
    out = extract_pattern(events, threshold=3)
    assert len(out) == 1
    assert out[0].candidate_action == "B"


def test_extract_proposal_carries_all_event_ids():
    events = [_make_event(user_action="x") for _ in range(5)]
    out = extract_pattern(events, threshold=5)
    assert sorted(out[0].based_on_event_ids) == sorted(e.event_id for e in events)


def test_extract_default_threshold_constant():
    """The default 5 is doc'd; pin it so changes are deliberate."""
    assert DEFAULT_THRESHOLD == 5


# ---------------------------------------------------------------------------
# SkillProposal queue
# ---------------------------------------------------------------------------


def _make_proposal(**overrides) -> SkillProposal:
    base = dict(
        proposal_id="skill-prop-001",
        proposed_at=NOW,
        status="pending",
        vertical="research",
        drift_mode="paper_collector",
        candidate_action="extract into a Markdown brief",
        candidate_duration_min=20,
        candidate_tank_credit_pct=5.0,
        based_on_event_count=5,
        based_on_event_ids=["e1", "e2", "e3", "e4", "e5"],
        extracted_at=NOW,
        notes="Test proposal.",
    )
    base.update(overrides)
    return SkillProposal(**base)


def test_skill_proposal_round_trip(tmp_path):
    home = tmp_path / "skill"
    p = _make_proposal()
    write_skill_proposal(p, home=home)
    got = read_skill_proposal(p.proposal_id, home=home, status="pending")
    assert got == p


def test_skill_proposal_is_frozen():
    p = _make_proposal()
    with pytest.raises(Exception):  # noqa: B017
        p.status = "accepted"  # type: ignore[misc]


def test_transition_pending_to_accepted(tmp_path):
    home = tmp_path / "skill"
    p = _make_proposal()
    write_skill_proposal(p, home=home)
    updated = transition_skill_proposal(
        p.proposal_id, home=home,
        from_status="pending", to_status="accepted",
    )
    assert updated.status == "accepted"
    assert list_skill_proposals(home=home, status="pending") == []
    assert len(list_skill_proposals(home=home, status="accepted")) == 1


def test_transition_rejects_same_status(tmp_path):
    home = tmp_path / "skill"
    p = _make_proposal()
    write_skill_proposal(p, home=home)
    with pytest.raises(ValueError):
        transition_skill_proposal(
            p.proposal_id, home=home,
            from_status="pending", to_status="pending",
        )


# ---------------------------------------------------------------------------
# run_extraction — end-to-end
# ---------------------------------------------------------------------------


def test_run_extraction_writes_proposals_to_pending(tmp_path):
    home = tmp_path / "skill"
    for i in range(5):
        write_override_event(
            vertical="research", drift_mode="paper_collector",
            user_action="extract into Markdown",
            home=home, ts=NOW - timedelta(days=i),
        )
    written = run_extraction(home=home, threshold=5, now=NOW)
    assert len(written) == 1
    pending = list_skill_proposals(home=home, status="pending")
    assert len(pending) == 1
    assert pending[0].vertical == "research"
    assert pending[0].drift_mode == "paper_collector"


def test_run_extraction_skips_already_proposed_buckets(tmp_path):
    home = tmp_path / "skill"
    # Seed: existing pending proposal for the same bucket.
    existing = _make_proposal(proposal_id="seed-001")
    write_skill_proposal(existing, home=home)
    # Now write 5 more events for the SAME bucket.
    for i in range(5):
        write_override_event(
            vertical="research", drift_mode="paper_collector",
            user_action="alt", home=home, ts=NOW - timedelta(days=i),
        )
    written = run_extraction(home=home, threshold=5, now=NOW)
    # Skipped because the bucket already has a pending proposal.
    assert written == []


def test_run_extraction_re_proposes_when_skip_disabled(tmp_path):
    home = tmp_path / "skill"
    existing = _make_proposal(proposal_id="seed-002")
    write_skill_proposal(existing, home=home)
    for i in range(5):
        write_override_event(
            vertical="research", drift_mode="paper_collector",
            user_action="alt", home=home, ts=NOW - timedelta(days=i),
        )
    written = run_extraction(
        home=home, threshold=5, now=NOW, skip_already_proposed=False,
    )
    assert len(written) == 1


def test_run_extraction_respects_window(tmp_path):
    home = tmp_path / "skill"
    # 5 events within window, 5 outside → only 5 inside count.
    for i in range(5):
        write_override_event(
            vertical="research", drift_mode="paper_collector",
            user_action="recent", home=home, ts=NOW - timedelta(days=i),
        )
    for i in range(5):
        write_override_event(
            vertical="research", drift_mode="paper_collector",
            user_action="old", home=home, ts=NOW - timedelta(days=60 + i),
        )
    written = run_extraction(home=home, threshold=5, window_days=30, now=NOW)
    assert len(written) == 1
    assert written[0].candidate_action == "recent"


def test_rejected_buckets_can_be_re_extracted(tmp_path):
    home = tmp_path / "skill"
    # Bucket has a REJECTED prior proposal.
    rejected = _make_proposal(proposal_id="seed-003", status="rejected")
    write_skill_proposal(rejected, home=home)
    for i in range(5):
        write_override_event(
            vertical="research", drift_mode="paper_collector",
            user_action="new attempt", home=home, ts=NOW - timedelta(days=i),
        )
    # Should re-propose because rejected doesn't count as "already proposed".
    written = run_extraction(home=home, threshold=5, now=NOW)
    assert len(written) == 1


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------


def _run(*args: str, env_overrides: dict | None = None,
         stdin: str | None = None) -> tuple[int, str, str]:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    p = subprocess.run(
        [sys.executable, "-m", "agent", *args],
        capture_output=True, text=True, timeout=30,
        env=env, input=stdin,
    )
    return p.returncode, p.stdout, p.stderr


def test_cli_log_override(tmp_path):
    home = tmp_path / "skill"
    rc, out, err = _run(
        "skillify", "log-override",
        "--vertical", "research",
        "--drift", "paper_collector",
        "--user-action", "wrote a one-page summary",
        "--home", str(home),
    )
    assert rc == 0, err
    parsed = json.loads(out)
    assert parsed["vertical"] == "research"
    assert parsed["user_action"] == "wrote a one-page summary"
    # File created.
    assert (home / "events.jsonl").exists()


def test_cli_extract_writes_proposals(tmp_path):
    home = tmp_path / "skill"
    # Seed 5 events via the API (faster than 5 CLI invocations).
    for i in range(5):
        write_override_event(
            vertical="research", drift_mode="paper_collector",
            user_action="alt", home=home, ts=NOW - timedelta(days=i),
        )
    rc, out, err = _run(
        "skillify", "extract",
        "--vertical", "research",
        "--threshold", "5",
        "--home", str(home),
    )
    assert rc == 0, err
    parsed = json.loads(out)
    assert len(parsed) == 1
    assert parsed[0]["vertical"] == "research"
    # Friendly summary on stderr.
    assert "1 new SkillProposal" in err


def test_cli_proposals_lists_pending(tmp_path):
    home = tmp_path / "skill"
    write_skill_proposal(_make_proposal(), home=home)
    rc, out, err = _run("skillify", "proposals", "--home", str(home))
    assert rc == 0, err
    assert len(json.loads(out)) == 1


def test_cli_review_default_summary(tmp_path):
    home = tmp_path / "skill"
    write_skill_proposal(_make_proposal(proposal_id="p1"), home=home)
    write_skill_proposal(_make_proposal(proposal_id="p2"), home=home)
    rc, out, _ = _run("skillify", "review", "--home", str(home))
    assert rc == 0
    assert "2 pending skill proposal" in out


def test_cli_review_cli_accepts_via_stdin(tmp_path):
    home = tmp_path / "skill"
    write_skill_proposal(_make_proposal(proposal_id="p1"), home=home)
    rc, out, _ = _run(
        "skillify", "review", "--cli", "--home", str(home),
        stdin="a\n",
    )
    assert rc == 0
    assert "accepted: p1" in out
    # File moved.
    assert list_skill_proposals(home=home, status="pending") == []
    assert len(list_skill_proposals(home=home, status="accepted")) == 1


def test_cli_review_cli_rejects_via_stdin(tmp_path):
    home = tmp_path / "skill"
    write_skill_proposal(_make_proposal(proposal_id="p1"), home=home)
    rc, out, _ = _run(
        "skillify", "review", "--cli", "--home", str(home),
        stdin="r\n",
    )
    assert rc == 0
    assert "rejected: p1" in out
    assert len(list_skill_proposals(home=home, status="rejected")) == 1


def test_cli_extract_rejects_bad_threshold(tmp_path):
    home = tmp_path / "skill"
    rc, _, err = _run(
        "skillify", "extract",
        "--threshold", "0",
        "--home", str(home),
    )
    assert rc == 2
    assert "must be >= 1" in err


def test_cli_extract_rejects_bad_window(tmp_path):
    home = tmp_path / "skill"
    rc, _, err = _run(
        "skillify", "extract",
        "--window-days", "0",
        "--home", str(home),
    )
    assert rc == 2
    assert "must be >= 1" in err
