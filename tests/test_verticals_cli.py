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


# ---------------------------------------------------------------------------
# `research compress` + `research express` (living-knowledge MVP)
# ---------------------------------------------------------------------------


def _seed_synthesis(home, *, run_id="syn-cli-001"):
    """Write a synthesis run to disk so `compress` has something to chew on."""
    home.mkdir(parents=True, exist_ok=True)
    from datetime import datetime, timezone

    from agent.research.synthesis import (
        MechanismCluster,
        SynthesisRun,
        write_synthesis_run,
    )

    cluster = MechanismCluster(
        cluster_id="c1",
        label="Replay buffer",
        mechanism_summary="Selective rehearsal of past experience prevents forgetting.",
        member_card_ids=("card-1", "card-2"),
    )
    run = SynthesisRun(
        run_id=run_id,
        generated_at=datetime.now(timezone.utc),
        window_days=30,
        min_cluster_size=2,
        method="fallback-heuristic",
        framework_name="(none)",
        input_card_count=2,
        clusters=(cluster,),
        unclustered_card_ids=(),
    )
    write_synthesis_run(run, home=home)
    return run


def test_research_compress_builds_from_latest_synthesis(home):
    _seed_synthesis(home)
    rc, out, err = _run("research", "compress", "--home", str(home), "--json")
    assert rc == 0, err
    data = json.loads(out)
    assert data["compression_id"].startswith("cmp-")
    assert data["source_synthesis_id"] == "syn-cli-001"
    assert len(data["level_0_nodes"]) == 1
    assert len(data["level_1_nodes"]) == 1
    assert len(data["level_2_nodes"]) == 2


def test_research_compress_errors_when_no_synthesis(home):
    home.mkdir(parents=True, exist_ok=True)
    rc, _out, err = _run("research", "compress", "--home", str(home))
    assert rc != 0
    assert "no synthesis runs" in err


def test_research_compress_list_after_build(home):
    _seed_synthesis(home)
    rc, _out, err = _run("research", "compress", "--home", str(home))
    assert rc == 0, err
    rc, out, err = _run("research", "compress", "--list", "--home", str(home))
    assert rc == 0, err
    assert "cmp-" in out
    assert "L0=1" in out
    assert "L1=1" in out
    assert "L2=2" in out


def test_research_express_record_and_list(home):
    _seed_synthesis(home)
    rc, out, err = _run("research", "compress", "--home", str(home), "--json")
    assert rc == 0, err
    compression = json.loads(out)
    l0_id = compression["level_0_nodes"][0]["node_id"]

    rc, out, err = _run(
        "research", "express",
        "--home", str(home),
        "--compression", compression["compression_id"],
        "--node", l0_id,
        "--modality", "narrative",
        "--title", "Cli smoke",
        "--content", "A short story about a librarian who forgets selectively.",
        "--json",
    )
    assert rc == 0, err
    expression = json.loads(out)
    assert expression["modality"] == "narrative"
    assert expression["source_node_id"] == l0_id
    assert expression["reveals"] is None

    rc, out, err = _run("research", "express", "--list", "--home", str(home))
    assert rc == 0, err
    assert expression["expression_id"] in out
    assert "narrative" in out


def test_research_express_reveal_closes_feedback_loop(home):
    _seed_synthesis(home)
    rc, out, _ = _run("research", "compress", "--home", str(home), "--json")
    compression = json.loads(out)
    l0_id = compression["level_0_nodes"][0]["node_id"]

    rc, out, _ = _run(
        "research", "express",
        "--home", str(home),
        "--compression", compression["compression_id"],
        "--node", l0_id,
        "--modality", "musical",
        "--title", "Replay harmony",
        "--content", "Three voices that fade unless a fourth voice cues them.",
        "--json",
    )
    expression = json.loads(out)

    rc, out, err = _run(
        "research", "express",
        "--home", str(home),
        "--reveal", expression["expression_id"],
        "--insight", "Replay needs emotional safety to function in teams.",
        "--feeds-back-to", l0_id,
        "--json",
    )
    assert rc == 0, err
    updated = json.loads(out)
    assert updated["expression_id"] == expression["expression_id"]
    assert "emotional safety" in (updated["reveals"] or "")
    assert updated["feeds_back_to_node_id"] == l0_id


def test_research_express_rejects_unknown_compression(home):
    home.mkdir(parents=True, exist_ok=True)
    rc, _out, err = _run(
        "research", "express",
        "--home", str(home),
        "--compression", "cmp-nope",
        "--node", "l0-00",
        "--modality", "narrative",
        "--title", "x",
        "--content", "y",
    )
    assert rc != 0
    assert "not found" in err.lower() or "no such" in err.lower()


def test_research_express_list_when_empty(home):
    home.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run("research", "express", "--list", "--home", str(home))
    assert rc == 0, err
    assert "no expressions yet" in out
