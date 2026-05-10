"""
Tests for PR-2 of Paul's week — the 4-feature bundle.

A. `loop urge --override-of` auto-emission (skillify OverrideEvent +
   the existing UrgeEvent in one CLI call).
B. `cross-vertical share-note` / `cross-vertical query` CLI surfaces
   around the existing programmatic functions.
C. `loop anchor --kind {faith,relational}` typed log + nightly count
   primitive.
D. `Priority.time_window` field — annotation only; back-compat default.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from agent.cross_vertical import write_note
from agent.founder_loop import (
    Anchor,
    Priority,
    count_anchors_per_day,
    read_anchors,
    write_anchor,
)
from agent.skillify import read_override_events


NOW = datetime(2026, 5, 11, 7, 0, 0, tzinfo=timezone.utc)  # Monday morning


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


# ===========================================================================
# Feature A — `loop urge --override-of` auto-emission
# ===========================================================================


def test_loop_urge_without_override_unchanged(tmp_path):
    """Backwards compat: omitting --override-of preserves old behavior
    (one UrgeEvent on disk; NO skillify event)."""
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"
    rc, out, err = _run(
        "loop", "urge",
        "--registry", str(registry),
        "--contracts", str(contracts),
        "entertainment", "--context", "checked twitter",
    )
    assert rc == 0, err
    parsed = json.loads(out)
    assert parsed["urge_type"] == "entertainment"
    assert "override_event" not in parsed
    # Skillify events should be empty (no override_of flag).
    assert read_override_events(home=tmp_path / "skill") == []


def test_loop_urge_with_override_of_emits_skillify_event(tmp_path):
    """When --override-of is set, BOTH the urge AND a skillify
    OverrideEvent are written, atomically from one command."""
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"

    # Override the default skillify home via env var so the test
    # is hermetic. The CLI handler uses default `~/.neuro_os_skillified/`
    # otherwise. We monkeypatch via HOME instead.
    rc, out, err = _run(
        "loop", "urge",
        "--registry", str(registry),
        "--contracts", str(contracts),
        "entertainment",
        "--context", "wrote one-page summary instead of paper extraction",
        "--override-of", "paper_collector",
        "--override-vertical", "research",
        env_overrides={"HOME": str(tmp_path)},  # redirects ~/.neuro_os_skillified/
    )
    assert rc == 0, err
    parsed = json.loads(out)
    assert parsed["urge_type"] == "entertainment"
    assert "override_event" in parsed
    assert parsed["override_event"]["vertical"] == "research"
    assert parsed["override_event"]["drift_mode"] == "paper_collector"
    assert (
        parsed["override_event"]["user_action"]
        == "wrote one-page summary instead of paper extraction"
    )
    # And the skillify on-disk log carries it.
    events = read_override_events(home=tmp_path / ".neuro_os_skillified")
    assert len(events) == 1
    assert events[0].drift_mode == "paper_collector"


def test_loop_urge_override_falls_back_to_urge_type_when_no_context(tmp_path):
    """If --context is empty, the OverrideEvent's user_action falls back
    to urge_type so the field is non-empty (Pydantic min_length=1)."""
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"
    rc, out, err = _run(
        "loop", "urge",
        "--registry", str(registry),
        "--contracts", str(contracts),
        "novelty",
        "--override-of", "topic_hopper",
        "--override-vertical", "research",
        env_overrides={"HOME": str(tmp_path)},
    )
    assert rc == 0, err
    parsed = json.loads(out)
    assert parsed["override_event"]["user_action"] == "novelty"


def test_loop_urge_override_default_vertical_is_founder_loop(tmp_path):
    registry = tmp_path / "registry.jsonl"
    contracts = tmp_path / "contracts.jsonl"
    rc, out, _ = _run(
        "loop", "urge",
        "--registry", str(registry),
        "--contracts", str(contracts),
        "entertainment", "--context", "did X",
        "--override-of", "fatigue",
        env_overrides={"HOME": str(tmp_path)},
    )
    assert rc == 0
    parsed = json.loads(out)
    assert parsed["override_event"]["vertical"] == "founder_loop"


# ===========================================================================
# Feature B — `cross-vertical` CLI subtree
# ===========================================================================


def test_cv_share_note_broadens_visibility(tmp_path):
    """share-note via CLI invokes the same share_note() logic as
    programmatic callers; visibility broadens from research-private
    to research+investment."""
    store = tmp_path / "cv.jsonl"
    note = write_note(
        source_vertical="research",
        note_kind="mechanism_card",
        payload={"title": "Pricing power"},
        store=store,
    )
    rc, out, err = _run(
        "cross-vertical", "share-note",
        "--note-id", note.id,
        "--with", "investment",
        "--store", str(store),
    )
    assert rc == 0, err
    parsed = json.loads(out)
    assert parsed["shared"] is True
    assert "investment" in parsed["add_visible"]


def test_cv_share_note_multiple_verticals(tmp_path):
    store = tmp_path / "cv.jsonl"
    note = write_note(
        source_vertical="research",
        note_kind="mechanism_card",
        payload={"x": 1},
        store=store,
    )
    rc, out, _ = _run(
        "cross-vertical", "share-note",
        "--note-id", note.id,
        "--with", "investment,startup",
        "--store", str(store),
    )
    assert rc == 0
    parsed = json.loads(out)
    assert sorted(parsed["add_visible"]) == ["investment", "startup"]


def test_cv_share_note_with_all_marker(tmp_path):
    store = tmp_path / "cv.jsonl"
    note = write_note(
        source_vertical="research",
        note_kind="mechanism_card",
        payload={"x": 1},
        store=store,
    )
    rc, _, _ = _run(
        "cross-vertical", "share-note",
        "--note-id", note.id,
        "--with", "__all__",
        "--store", str(store),
    )
    assert rc == 0


def test_cv_share_note_missing_id(tmp_path):
    store = tmp_path / "cv.jsonl"
    rc, _, err = _run(
        "cross-vertical", "share-note",
        "--note-id", "ghost",
        "--with", "investment",
        "--store", str(store),
    )
    assert rc == 2
    assert "not found" in err


def test_cv_share_note_invalid_vertical(tmp_path):
    store = tmp_path / "cv.jsonl"
    note = write_note(
        source_vertical="research", note_kind="x", payload={}, store=store,
    )
    rc, _, err = _run(
        "cross-vertical", "share-note",
        "--note-id", note.id,
        "--with", "made_up_vertical",
        "--store", str(store),
    )
    assert rc == 2
    assert "unknown" in err.lower()


def test_cv_query_respects_visibility(tmp_path):
    """Default-PRIVATE: research-only notes don't surface for investment
    reader."""
    store = tmp_path / "cv.jsonl"
    write_note(
        source_vertical="research", note_kind="mechanism_card",
        payload={"x": 1}, store=store,
    )
    rc, out, _ = _run(
        "cross-vertical", "query",
        "--reader", "investment",
        "--store", str(store),
    )
    assert rc == 0
    assert json.loads(out) == []


def test_cv_query_returns_visible_notes(tmp_path):
    store = tmp_path / "cv.jsonl"
    write_note(
        source_vertical="research", note_kind="mechanism_card",
        payload={"x": 1}, store=store,
        visible_to=["research", "investment"],
    )
    rc, out, _ = _run(
        "cross-vertical", "query",
        "--reader", "investment",
        "--store", str(store),
    )
    assert rc == 0
    notes = json.loads(out)
    assert len(notes) == 1
    assert notes[0]["note_kind"] == "mechanism_card"


# ===========================================================================
# Feature C — `loop anchor` faith / relational log
# ===========================================================================


def test_anchor_round_trip(tmp_path):
    a = write_anchor(
        kind="faith",
        context="5:50am prayer + walk + plan done",
        home=tmp_path,
        ts=NOW,
    )
    assert a.kind == "faith"
    rows = read_anchors(home=tmp_path)
    assert len(rows) == 1
    assert rows[0] == a


def test_anchor_is_frozen():
    a = Anchor(
        anchor_id="x", ts=NOW, kind="faith",
        context="prayer",
    )
    with pytest.raises(Exception):  # noqa: B017 (Pydantic ValidationError)
        a.kind = "relational"  # type: ignore[misc]


def test_count_anchors_per_day_dedups_same_day(tmp_path):
    """Multiple anchors on the same calendar day count as ONE day-hit."""
    write_anchor(kind="faith", context="morning", home=tmp_path,
                 ts=NOW.replace(hour=6))
    write_anchor(kind="faith", context="midday", home=tmp_path,
                 ts=NOW.replace(hour=13))
    write_anchor(kind="faith", context="evening", home=tmp_path,
                 ts=NOW.replace(hour=22))
    hits, window = count_anchors_per_day(
        home=tmp_path, kind="faith", days=7, now=NOW + timedelta(days=1),
    )
    assert (hits, window) == (1, 7)


def test_count_anchors_per_day_separate_days(tmp_path):
    """7 anchors on 7 distinct calendar days, with ``now`` set to the
    last anchor's day → 7 of the last 7 days hit (the ideal Paul-week
    rendering)."""
    for i in range(7):
        write_anchor(kind="faith", context=f"day {i}", home=tmp_path,
                     ts=NOW + timedelta(days=i))
    # ``now`` = the last anchor's day so the 7-day window covers them all.
    hits, window = count_anchors_per_day(
        home=tmp_path, kind="faith", days=7, now=NOW + timedelta(days=6),
    )
    assert (hits, window) == (7, 7)


def test_count_anchors_per_day_excludes_outside_window(tmp_path):
    """Anchors older than the window aren't counted."""
    # Two old (out of window) + two recent (in window).
    write_anchor(kind="faith", context="old1", home=tmp_path,
                 ts=NOW - timedelta(days=20))
    write_anchor(kind="faith", context="old2", home=tmp_path,
                 ts=NOW - timedelta(days=15))
    write_anchor(kind="faith", context="new1", home=tmp_path,
                 ts=NOW - timedelta(days=2))
    write_anchor(kind="faith", context="new2", home=tmp_path, ts=NOW)
    hits, _ = count_anchors_per_day(
        home=tmp_path, kind="faith", days=7, now=NOW,
    )
    assert hits == 2


def test_count_anchors_per_day_filters_by_kind(tmp_path):
    write_anchor(kind="faith", context="prayer", home=tmp_path, ts=NOW)
    write_anchor(kind="relational", context="taylor", home=tmp_path, ts=NOW)
    faith_hits, _ = count_anchors_per_day(
        home=tmp_path, kind="faith", days=7, now=NOW + timedelta(days=1),
    )
    rel_hits, _ = count_anchors_per_day(
        home=tmp_path, kind="relational", days=7, now=NOW + timedelta(days=1),
    )
    assert faith_hits == 1
    assert rel_hits == 1


def test_anchor_atomic_write_no_partial_lines(tmp_path):
    """20 sequential writes produce exactly 20 valid JSON lines."""
    for i in range(20):
        write_anchor(
            kind="faith", context=f"entry {i}",
            home=tmp_path, ts=NOW + timedelta(seconds=i),
        )
    text = (tmp_path / "anchors.jsonl").read_text()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 20
    for line in lines:
        json.loads(line)  # raises if malformed


def test_cli_loop_anchor(tmp_path):
    rc, out, err = _run(
        "loop", "anchor",
        "--kind", "faith",
        "--context", "morning prayer + walk done",
        "--home", str(tmp_path),
    )
    assert rc == 0, err
    parsed = json.loads(out)
    assert parsed["kind"] == "faith"
    assert parsed["context"] == "morning prayer + walk done"
    assert (tmp_path / "anchors.jsonl").exists()


def test_cli_loop_anchor_relational(tmp_path):
    rc, out, _ = _run(
        "loop", "anchor",
        "--kind", "relational",
        "--context", "Taylor: cooked dinner together",
        "--home", str(tmp_path),
    )
    assert rc == 0
    parsed = json.loads(out)
    assert parsed["kind"] == "relational"


# ===========================================================================
# Feature D — `Priority.time_window` field
# ===========================================================================


def _priority(**overrides):
    base = dict(
        title="Read Constitutional AI paper",
        evidence_type="commit_pushed",
        evidence_target="mechanism_card_extracted",
        weight=2,
    )
    base.update(overrides)
    return Priority(**base)


def test_priority_time_window_default_none():
    """Back-compat: omitting time_window leaves it None."""
    p = _priority()
    assert p.time_window is None


def test_priority_time_window_accepts_valid_format():
    """HH:MM-HH:MM format accepted."""
    for window in ("07:00-09:00", "00:00-23:59", "13:30-15:00"):
        p = _priority(time_window=window)
        assert p.time_window == window


def test_priority_time_window_rejects_malformed():
    """Garbage input rejected at construction time (Law 1)."""
    for bad in (
        "7:00-9:00",         # single-digit hour
        "07:00",             # no end window
        "07-09",             # no minutes
        "07:00 to 09:00",    # wrong separator
        "25:00-09:00",       # invalid hour
        "not a window",
    ):
        with pytest.raises(Exception):  # noqa: B017 (Pydantic ValidationError)
            _priority(time_window=bad)


def test_priority_round_trips_with_time_window():
    """JSON round-trip preserves time_window."""
    p = _priority(time_window="09:00-12:30")
    body = p.model_dump_json()
    p2 = Priority.model_validate_json(body)
    assert p2.time_window == "09:00-12:30"


def test_legacy_priority_json_without_time_window_still_loads():
    """A serialized priority from before this PR (no time_window key)
    deserializes fine — the field defaults to None."""
    legacy = {
        "title": "Old priority",
        "evidence_type": "commit_pushed",
        "evidence_target": "x",
        "weight": 1,
    }
    p = Priority.model_validate(legacy)
    assert p.time_window is None
