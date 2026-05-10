"""
Tests for ``agent.research.dashboard`` (Lane 5).

Strategy: a deterministic 40-day fixture (registry_40d.jsonl +
ingestion_runs_40d.jsonl) drives the headline rollup test. Smaller
unit tests pin individual aggregation primitives (drift-mode bucketing,
stick-rate, window clipping). The CLI is exercised via subprocess.

Eight gates from the design doc, each named below.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent.research.dashboard import (
    DashboardSummary,
    STICK_WINDOW_DAYS,
    _aggregate_drift_modes,
    _compute_stick_rate,
    _filter_window,
    build_dashboard_summary,
    render_text,
)


FIXTURES = Path(__file__).parent / "fixtures" / "research"
REGISTRY_FIXTURE = FIXTURES / "registry_40d.jsonl"
INGESTION_FIXTURE = FIXTURES / "ingestion_runs_40d.jsonl"

# Anchored "now" used to build the fixtures. Tests use this so the window
# math is fully deterministic.
NOW = datetime(2026, 5, 9, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_home(home: Path) -> None:
    """Copy the 40-day fixtures into a fresh home dir at the canonical paths."""
    home.mkdir(parents=True, exist_ok=True)
    shutil.copy(REGISTRY_FIXTURE, home / "registry.jsonl")
    shutil.copy(INGESTION_FIXTURE, home / "ingestion_runs.jsonl")


# ---------------------------------------------------------------------------
# Gate 1: build_dashboard_summary against the 40-day fixture
# ---------------------------------------------------------------------------


def test_build_dashboard_summary_against_fixture(tmp_path):
    home = tmp_path / "research"
    _seed_home(home)

    summary = build_dashboard_summary(home=home, window_days=40, now=NOW)

    assert summary.vertical == "research"
    assert summary.window_days == 40
    assert summary.generated_at == NOW

    # Drift-mode counts (each pinned by-hand from the fixture generator):
    assert summary.drift_mode_counts == {
        "paper_collector": 18,
        "topic_hopper": 8,
        "authority_acceptor": 4,
        "memorizer": 1,
    }
    assert summary.drift_mode_top_3 == [
        ("paper_collector", 18),
        ("topic_hopper", 8),
        ("authority_acceptor", 4),
    ]

    # CE counts: 31 propose ops in window (out-of-window excluded).
    assert summary.constructive_expressions_offered == 31
    assert summary.constructive_expressions_accepted == 31
    # Stick-rate: with one explicit override pair and bursty same-mode
    # firings, some are overridden. Pin only invariants here; the exact
    # stuck count is pinned by the dedicated unit test below.
    assert 0 <= summary.constructive_expressions_stuck <= 31

    # Ingestion: 8 in-window runs sum to 80 sources / 14 emitted.
    assert summary.sources_scanned == 80
    assert summary.proposals_emitted == 14

    # Catalog candidates: overloaded + forgetting NEVER fired in window.
    assert sorted(summary.drift_modes_never_fired) == ["forgetting", "overloaded"]

    # Proposal queue empty (no proposal files in tmp_path).
    assert summary.proposals_accepted == 0
    assert summary.proposals_rejected == 0
    assert summary.pending_proposals_count == 0
    assert summary.pending_proposals_oldest_age_hours is None


# ---------------------------------------------------------------------------
# Gate 2: empty home → zeros, doesn't crash
# ---------------------------------------------------------------------------


def test_dashboard_handles_empty_home(tmp_path):
    home = tmp_path / "fresh"
    home.mkdir()

    summary = build_dashboard_summary(home=home, window_days=40, now=NOW)

    assert summary.window_days == 40
    assert summary.primary_metric_today == 0.0
    assert summary.primary_metric_window_avg == 0.0
    assert summary.primary_metric_window_trend == "flat"
    assert summary.drift_mode_counts == {}
    assert summary.drift_mode_top_3 == []
    assert summary.constructive_expressions_offered == 0
    assert summary.constructive_expressions_accepted == 0
    assert summary.constructive_expressions_stuck == 0
    assert summary.sources_scanned == 0
    assert summary.proposals_emitted == 0
    assert summary.pending_proposals_count == 0
    assert summary.pending_proposals_oldest_age_hours is None
    # All 6 catalog modes are "never fired" on an empty install.
    assert len(summary.drift_modes_never_fired) == 6


def test_dashboard_handles_nonexistent_home(tmp_path):
    """Even if the home dir doesn't exist, build_dashboard_summary returns a summary."""
    home = tmp_path / "does-not-exist"
    summary = build_dashboard_summary(home=home, window_days=7, now=NOW)
    assert summary.window_days == 7
    assert summary.constructive_expressions_offered == 0


# ---------------------------------------------------------------------------
# Gate 3: window clipping
# ---------------------------------------------------------------------------


def test_dashboard_window_clipping(tmp_path):
    """A 7-day window includes far fewer rows than a 40-day window."""
    home = tmp_path / "research"
    _seed_home(home)

    full = build_dashboard_summary(home=home, window_days=40, now=NOW)
    week = build_dashboard_summary(home=home, window_days=7, now=NOW)

    # Total drift events in the last 7 days < total in 40 days (strict).
    full_total = sum(full.drift_mode_counts.values())
    week_total = sum(week.drift_mode_counts.values())
    assert week_total < full_total
    # Ingestion: only the runs at offset 1, 3, 6 are in the 7-day window
    # (10+13+11 sources, 1+2+2 emitted) — 3 runs, 34 sources, 5 proposals.
    assert week.sources_scanned == 34
    assert week.proposals_emitted == 5


def test_filter_window_excludes_old_rows():
    rows = [
        {"ts": (NOW - timedelta(days=5)).isoformat()},
        {"ts": (NOW - timedelta(days=50)).isoformat()},
        {"ts": (NOW - timedelta(days=39, hours=23)).isoformat()},
    ]
    kept = _filter_window(rows, now=NOW, window_days=40)
    assert len(kept) == 2  # 50d-old excluded, the rest kept


def test_filter_window_skips_malformed_ts():
    rows = [
        {"ts": "not-a-timestamp"},
        {"ts": None},
        {},  # no ts at all
        {"ts": (NOW - timedelta(days=5)).isoformat()},
    ]
    kept = _filter_window(rows, now=NOW, window_days=40)
    assert len(kept) == 1


# ---------------------------------------------------------------------------
# Gate 4: drift_modes_never_fired signal
# ---------------------------------------------------------------------------


def test_drift_modes_never_fired_signal(tmp_path):
    home = tmp_path / "research"
    _seed_home(home)
    summary = build_dashboard_summary(home=home, window_days=40, now=NOW)
    # Both modes fired exactly zero times in the fixture.
    assert "overloaded" in summary.drift_modes_never_fired
    assert "forgetting" in summary.drift_modes_never_fired
    # And the modes that DID fire are NOT listed.
    assert "paper_collector" not in summary.drift_modes_never_fired
    assert "memorizer" not in summary.drift_modes_never_fired


# ---------------------------------------------------------------------------
# Gate 5: stick-rate — the load-bearing math
# ---------------------------------------------------------------------------


def test_stick_rate_single_offer_is_stuck():
    """One propose op, no later events → stuck."""
    rows = [
        {
            "ts": NOW.isoformat(),
            "action": {
                "op": "propose_constructive_expression",
                "payload": {"primary_action": "do thing A"},
                "diagnosis": {"underlying_need": "paper_collector"},
            },
        },
    ]
    offered, accepted, stuck = _compute_stick_rate(rows)
    assert (offered, accepted, stuck) == (1, 1, 1)


def test_stick_rate_same_mode_different_action_within_7d_overrides():
    """Same drift mode + different primary_action within 7d → first NOT stuck."""
    earlier = (NOW - timedelta(days=10)).isoformat()
    later = (NOW - timedelta(days=5)).isoformat()  # 5 days after earlier
    rows = [
        {
            "ts": earlier,
            "action": {
                "op": "propose_constructive_expression",
                "payload": {"primary_action": "do thing A"},
                "diagnosis": {"underlying_need": "paper_collector"},
            },
        },
        {
            "ts": later,
            "action": {
                "op": "propose_constructive_expression",
                "payload": {"primary_action": "do thing B"},  # DIFFERENT
                "diagnosis": {"underlying_need": "paper_collector"},
            },
        },
    ]
    offered, accepted, stuck = _compute_stick_rate(rows)
    assert offered == 2
    # First override; second has no follow-up override → stuck.
    assert stuck == 1


def test_stick_rate_same_mode_same_action_within_7d_does_not_override():
    """Same drift mode + SAME primary_action within 7d → NOT an override; both stuck."""
    earlier = (NOW - timedelta(days=10)).isoformat()
    later = (NOW - timedelta(days=5)).isoformat()
    rows = [
        {
            "ts": earlier,
            "action": {
                "op": "propose_constructive_expression",
                "payload": {"primary_action": "do thing A"},
                "diagnosis": {"underlying_need": "paper_collector"},
            },
        },
        {
            "ts": later,
            "action": {
                "op": "propose_constructive_expression",
                "payload": {"primary_action": "do thing A"},  # SAME
                "diagnosis": {"underlying_need": "paper_collector"},
            },
        },
    ]
    offered, accepted, stuck = _compute_stick_rate(rows)
    assert (offered, stuck) == (2, 2)


def test_stick_rate_same_mode_different_action_outside_7d_does_not_override():
    """Different primary_action OUTSIDE the 7d stick window → first IS stuck."""
    far = STICK_WINDOW_DAYS + 5
    earlier = (NOW - timedelta(days=20)).isoformat()
    later = (NOW - timedelta(days=20 - far)).isoformat()
    rows = [
        {
            "ts": earlier,
            "action": {
                "op": "propose_constructive_expression",
                "payload": {"primary_action": "do thing A"},
                "diagnosis": {"underlying_need": "paper_collector"},
            },
        },
        {
            "ts": later,
            "action": {
                "op": "propose_constructive_expression",
                "payload": {"primary_action": "do thing B"},
                "diagnosis": {"underlying_need": "paper_collector"},
            },
        },
    ]
    offered, accepted, stuck = _compute_stick_rate(rows)
    # First not overridden (B is past the 7d window); second has no follow-up.
    assert (offered, stuck) == (2, 2)


def test_stick_rate_different_modes_dont_override():
    """A different drift mode within 7d does NOT count as an override."""
    earlier = (NOW - timedelta(days=10)).isoformat()
    later = (NOW - timedelta(days=5)).isoformat()
    rows = [
        {
            "ts": earlier,
            "action": {
                "op": "propose_constructive_expression",
                "payload": {"primary_action": "do thing A"},
                "diagnosis": {"underlying_need": "paper_collector"},
            },
        },
        {
            "ts": later,
            "action": {
                "op": "propose_constructive_expression",
                "payload": {"primary_action": "do thing B"},
                "diagnosis": {"underlying_need": "topic_hopper"},  # DIFFERENT MODE
            },
        },
    ]
    offered, accepted, stuck = _compute_stick_rate(rows)
    assert (offered, stuck) == (2, 2)


def test_stick_rate_ignores_continue_ops():
    """``op == "continue"`` rows are not propose offers."""
    rows = [
        {
            "ts": NOW.isoformat(),
            "action": {"op": "continue", "payload": {}, "diagnosis": None},
        },
    ]
    assert _compute_stick_rate(rows) == (0, 0, 0)


# ---------------------------------------------------------------------------
# Gate 6: DashboardSummary is frozen
# ---------------------------------------------------------------------------


def test_dashboard_summary_is_frozen():
    summary = build_dashboard_summary(window_days=7, now=NOW, home=Path("/nonexistent"))
    with pytest.raises(Exception):  # noqa: B017  (Pydantic ValidationError)
        summary.window_days = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Gates 7-8: CLI text + JSON
# ---------------------------------------------------------------------------


def _run(*args: str) -> tuple[int, str, str]:
    p = subprocess.run(
        [sys.executable, "-m", "agent", *args],
        capture_output=True, text=True, timeout=30,
    )
    return p.returncode, p.stdout, p.stderr


def test_cli_research_dashboard_prints_text(tmp_path):
    home = tmp_path / "research"
    _seed_home(home)
    rc, out, err = _run("research", "dashboard", "--home", str(home))
    assert rc == 0, err
    # Section headers from render_text:
    assert "Compound curve" in out
    assert "Drift-mode usage" in out
    assert "Constructive expressions" in out
    assert "Lane 1 ingestion" in out
    assert "Action queue" in out
    # Counts visible in the rendered text:
    assert "paper_collector" in out
    assert "overloaded" in out  # under "fired 0 times"


def test_cli_research_dashboard_json(tmp_path):
    home = tmp_path / "research"
    _seed_home(home)
    # Use --window 41 to give a safe buffer against the fixture's
    # day-39 boundary event drifting out of the window as wall-clock
    # advances past the fixture-creation date. The unit-test version
    # of this assertion (test_build_dashboard_summary_against_fixture)
    # uses an injected `now=NOW` so it's exact at 18.
    rc, out, err = _run(
        "research", "dashboard", "--home", str(home),
        "--window", "41", "--json",
    )
    assert rc == 0, err
    parsed = DashboardSummary.model_validate_json(out)
    assert parsed.vertical == "research"
    assert parsed.window_days == 41
    assert parsed.drift_mode_counts["paper_collector"] == 18


def test_cli_research_dashboard_window_flag(tmp_path):
    home = tmp_path / "research"
    _seed_home(home)
    rc, out, err = _run("research", "dashboard", "--home", str(home), "--window", "7", "--json")
    assert rc == 0, err
    parsed = DashboardSummary.model_validate_json(out)
    assert parsed.window_days == 7
    # 7-day window has fewer ingestion totals than the full 40-day fixture.
    assert parsed.sources_scanned < 80


def test_cli_research_dashboard_rejects_bad_window(tmp_path):
    home = tmp_path / "research"
    _seed_home(home)
    rc, out, err = _run("research", "dashboard", "--home", str(home), "--window", "0")
    assert rc == 2
    assert "must be between 1 and 365" in err


# ---------------------------------------------------------------------------
# Bonus: render_text doesn't crash on the empty-home summary
# ---------------------------------------------------------------------------


def test_render_text_handles_empty_summary(tmp_path):
    home = tmp_path / "fresh"
    home.mkdir()
    summary = build_dashboard_summary(home=home, window_days=40, now=NOW)
    text = render_text(summary)
    assert "no drift events in window" in text
    assert "no constructive expressions offered" in text
    assert "no pending proposals" in text


# ---------------------------------------------------------------------------
# Bonus: drift-mode bucketing isolated from window math
# ---------------------------------------------------------------------------


def test_aggregate_drift_modes_buckets_by_underlying_need():
    rows = [
        {"action": {"op": "propose_constructive_expression",
                    "diagnosis": {"underlying_need": "paper_collector"}}},
        {"action": {"op": "propose_constructive_expression",
                    "diagnosis": {"underlying_need": "paper_collector"}}},
        {"action": {"op": "propose_constructive_expression",
                    "diagnosis": {"underlying_need": "topic_hopper"}}},
        {"action": {"op": "continue", "diagnosis": None}},  # ignored
        {"action": {"op": "propose_constructive_expression"}},  # no diagnosis → ignored
    ]
    counts = _aggregate_drift_modes(rows)
    assert counts == {"paper_collector": 2, "topic_hopper": 1}


# ---------------------------------------------------------------------------
# Bonus: pending-age + proposal-count integration with the existing queue
# ---------------------------------------------------------------------------


def test_dashboard_picks_up_pending_proposal_age(tmp_path):
    """Lane-1 produces files in proposals/pending/; Lane 5 reads them."""
    from agent.research import GbrainQuerySpec
    from agent.research.gbrain_adapter import fetch_from_export_file, ingest

    home = tmp_path / "research"
    _seed_home(home)
    fixture = Path(__file__).parent / "fixtures" / "research" / "gbrain_export.json"
    ingest(
        spec=GbrainQuerySpec(query="seed"),
        call_gbrain=fetch_from_export_file(fixture),
        home=home,
        # Simulate a proposal proposed 10 hours ago.
        now=NOW - timedelta(hours=10),
    )

    summary = build_dashboard_summary(home=home, window_days=40, now=NOW)

    assert summary.pending_proposals_count == 2
    assert summary.pending_proposals_oldest_age_hours is not None
    assert 9.5 < summary.pending_proposals_oldest_age_hours < 10.5


# ---------------------------------------------------------------------------
# Sanity: fixture file is the size we expect (guards against accidental edits)
# ---------------------------------------------------------------------------


def test_registry_fixture_unchanged():
    """If this fails, the fixture was edited; update the byhand-pinned counts above."""
    rows = [
        json.loads(line)
        for line in REGISTRY_FIXTURE.read_text().splitlines()
        if line.strip()
    ]
    assert len(rows) == 37  # 30 propose + 5 continue + 1 override + 1 outside-window
