"""
Smoke tests for the verticals CLI (research / invest / startup).

Each vertical exposes 3 top-level subcommands: onboard / tick /
nightly. These tests drive the CLI via subprocess to verify the
end-to-end path (parse → factory → hook → output).
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


def _run(*args: str, env: dict | None = None) -> tuple[int, str, str]:
    p = subprocess.run(
        [sys.executable, "-m", "agent", *args],
        capture_output=True, text=True, timeout=30,
        env=env,
    )
    return p.returncode, p.stdout, p.stderr


# ---------------------------------------------------------------------------
# `research` subcommands
# ---------------------------------------------------------------------------


def test_research_nightly_on_empty_home(home):
    rc, out, err = _run("research", "nightly", "--home", str(home))
    assert rc == 0, err
    summary = json.loads(out)
    assert summary["vertical"] == "research"
    assert summary["primary_metric_label"] == "mechanism cards/day"
    assert summary["primary_resource_label"] == "papers read"


def test_research_tick_with_drift_emits_diagnosis(home):
    rc, out, err = _run(
        "research", "tick",
        "--drift", "paper_collector",
        "--home", str(home),
        "--dry-run",
    )
    assert rc == 0, err
    result = json.loads(out)
    assert result["action"]["op"] == "propose_constructive_expression"
    assert result["action"]["diagnosis"]["underlying_need"] == "paper_collector"


def test_research_onboard_signs_contract(home, tmp_path):
    priorities_file = tmp_path / "priorities.json"
    priorities_file.write_text(json.dumps([
        {
            "title": "extract mechanism from Friston 2010",
            "evidence_type": "paper_read",
            "evidence_target": "MechanismCard for predictive coding",
            "weight": 3,
            "thesis_id": "thesis-001",
        },
    ]))
    rc, out, err = _run(
        "research", "onboard",
        "--priorities-file", str(priorities_file),
        "--home", str(home),
        "--active-thesis-id", "thesis-001",
    )
    assert rc == 0, err
    contract = json.loads(out)
    assert contract["active_thesis_id"] == "thesis-001"
    assert len(contract["priorities"]) == 1


# ---------------------------------------------------------------------------
# `invest` subcommands (advisory-only)
# ---------------------------------------------------------------------------


def test_invest_nightly_carries_advisory_only_flag(home):
    rc, out, err = _run("invest", "nightly", "--home", str(home))
    assert rc == 0, err
    summary = json.loads(out)
    assert summary["vertical"] == "investment"
    assert summary["extra"]["advisory_only"] is True


def test_invest_tick_with_drift_emits_diagnosis(home):
    rc, out, err = _run(
        "invest", "tick",
        "--drift", "narrative_following",
        "--home", str(home),
        "--dry-run",
    )
    assert rc == 0, err
    result = json.loads(out)
    assert result["action"]["op"] == "propose_constructive_expression"
    assert result["action"]["diagnosis"]["underlying_need"] == "narrative_following"
    assert result["action"]["payload"]["advisory_only"] is True


def test_invest_onboard_signs_contract(home, tmp_path):
    priorities_file = tmp_path / "priorities.json"
    priorities_file.write_text(json.dumps([
        {
            "title": "document AAPL thesis",
            "evidence_type": "thesis_documented",
            "evidence_target": "PositionThesis for AAPL",
            "weight": 2,
            "instrument": "AAPL",
        },
    ]))
    rc, out, err = _run(
        "invest", "onboard",
        "--priorities-file", str(priorities_file),
        "--home", str(home),
    )
    assert rc == 0, err
    contract = json.loads(out)
    assert contract["advisory_only"] is True


# ---------------------------------------------------------------------------
# `startup` subcommands
# ---------------------------------------------------------------------------


def test_startup_nightly(home):
    rc, out, err = _run("startup", "nightly", "--home", str(home))
    assert rc == 0, err
    summary = json.loads(out)
    assert summary["vertical"] == "startup"
    assert summary["primary_metric_label"] == "strategic continuity score"


def test_startup_tick_with_drift_emits_diagnosis(home):
    rc, out, err = _run(
        "startup", "tick",
        "--drift", "broadcasting",
        "--home", str(home),
        "--dry-run",
    )
    assert rc == 0, err
    result = json.loads(out)
    assert result["action"]["op"] == "propose_constructive_expression"
    assert result["action"]["diagnosis"]["underlying_need"] == "broadcasting"


def test_startup_onboard_requires_active_hypothesis_id(home, tmp_path):
    priorities_file = tmp_path / "priorities.json"
    priorities_file.write_text(json.dumps([
        {
            "title": "capture 3 audience signals",
            "evidence_type": "audience_signal_captured",
            "evidence_target": "3 signals",
            "weight": 2,
            "hypothesis_id": "hyp-001",
        },
    ]))
    rc, out, err = _run(
        "startup", "onboard",
        "--priorities-file", str(priorities_file),
        "--home", str(home),
        "--active-hypothesis-id", "hyp-001",
    )
    assert rc == 0, err
    contract = json.loads(out)
    assert contract["active_hypothesis_id"] == "hyp-001"


def test_startup_onboard_thesis_pivot_cap_enforced(home, tmp_path):
    """The --budget flag on startup is thesis-pivots/day; hard cap is 1."""
    priorities_file = tmp_path / "priorities.json"
    priorities_file.write_text(json.dumps([
        {
            "title": "x",
            "evidence_type": "hypothesis_validated",
            "evidence_target": "y",
            "weight": 1,
            "hypothesis_id": "hyp-001",
        },
    ]))
    rc, out, err = _run(
        "startup", "onboard",
        "--priorities-file", str(priorities_file),
        "--home", str(home),
        "--active-hypothesis-id", "hyp-001",
        "--budget", "5",  # over cap
    )
    # The handler raises ValueError; argparse propagates it as exit code != 0.
    assert rc != 0
    assert "hard cap is 1" in err or "hard cap is 1" in out


# ---------------------------------------------------------------------------
# Drift choice validation: invalid drift values are rejected by argparse
# ---------------------------------------------------------------------------


def test_research_tick_rejects_unknown_drift(home):
    rc, out, err = _run(
        "research", "tick",
        "--drift", "fake_failure_mode",
        "--home", str(home),
        "--dry-run",
    )
    assert rc != 0
    assert "invalid choice" in err.lower() or "argument" in err.lower()


def test_invest_tick_rejects_research_drift(home):
    """Cross-vertical drift names must not leak — invest can't take 'paper_collector'."""
    rc, out, err = _run(
        "invest", "tick",
        "--drift", "paper_collector",  # research's term, not invest's
        "--home", str(home),
        "--dry-run",
    )
    assert rc != 0
