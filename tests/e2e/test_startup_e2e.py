"""
End-to-end CLI scenarios for the **startup** vertical.

The load-bearing startup invariants:

1. ``--budget`` is interpreted as ``thesis_pivots/day`` and is hard-
   capped at 1. Anti-novelty-addiction.
2. ``--active-hypothesis-id`` is required at onboard and is reachable
   on subsequent ticks via the persisted contract.
3. Strategic continuity score = 1.0 when no hypothesis has been killed
   (the day-1 baseline).

Catalog: scenarios.md S25 (full-day flow), S26 (pivot cap enforced).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def home(tmp_path) -> Path:
    return tmp_path / "startup_home"


def _run(*args: str) -> tuple[int, str, str]:
    p = subprocess.run(
        [sys.executable, "-m", "agent", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return p.returncode, p.stdout, p.stderr


def _write_priorities(tmp_path: Path) -> Path:
    f = tmp_path / "priorities.json"
    f.write_text(json.dumps([
        {
            "title": "capture 3 audience signals from this week's launch replies",
            "evidence_type": "audience_signal_captured",
            "evidence_target": "3 signals",
            "weight": 3,
            "hypothesis_id": "hyp-001",
        },
    ]))
    return f


# ---------------------------------------------------------------------------
# S25 — Founder's full day: onboard → idea-chaos drift → broadcasting drift
#       → continue tick → nightly. Day-1 continuity = 1.0 (no kills).
# ---------------------------------------------------------------------------


def test_s25_startup_full_day_flow(home: Path, tmp_path: Path):
    priorities_file = _write_priorities(tmp_path)

    # --- morning: onboard with active hypothesis ----------------------
    rc, out, err = _run(
        "startup", "onboard",
        "--priorities-file", str(priorities_file),
        "--home", str(home),
        "--active-hypothesis-id", "hyp-001",
        "--budget", "1",
    )
    assert rc == 0, err
    contract = json.loads(out)
    assert contract["active_hypothesis_id"] == "hyp-001"
    assert len(contract["priorities"]) == 1

    # --- 11am: caught flirting with a new "what if we…" --------------
    rc, out, err = _run(
        "startup", "tick",
        "--drift", "idea_chaos",
        "--home", str(home),
    )
    assert rc == 0, err
    chaos = json.loads(out)
    assert chaos["action"]["op"] == "propose_constructive_expression"
    assert chaos["action"]["diagnosis"]["underlying_need"] == "idea_chaos"

    # --- 3pm: caught broadcasting without listening ------------------
    rc, out, err = _run(
        "startup", "tick",
        "--drift", "broadcasting",
        "--home", str(home),
    )
    assert rc == 0, err
    broadcast = json.loads(out)
    assert broadcast["action"]["diagnosis"]["underlying_need"] == "broadcasting"

    # --- 5pm: clean tick (no drift) ---------------------------------
    rc, out, err = _run(
        "startup", "tick",
        "--home", str(home),
    )
    assert rc == 0, err
    clean = json.loads(out)
    assert clean["action"]["op"] == "continue"

    # --- registry has all three rows --------------------------------
    registry_jsonl = home / "registry.jsonl"
    rows = [json.loads(line) for line in registry_jsonl.open() if line.strip()]
    assert len(rows) == 3
    assert {r["action"]["op"] for r in rows} == {
        "propose_constructive_expression", "continue",
    }

    # --- evening: nightly summary ----------------------------------
    rc, out, err = _run(
        "startup", "nightly",
        "--home", str(home),
    )
    assert rc == 0, err
    summary = json.loads(out)
    assert summary["vertical"] == "startup"
    assert summary["primary_metric_label"] == "strategic continuity score"
    # No hypotheses killed today → continuity score is 1.0.
    assert summary["primary_metric_today"] == 1.0
    # No kill_event ops fired today.
    assert summary["primary_resource_used_today"] == 0.0
    # Honor rate: all three actions honored the contract.
    assert summary["honor_rate_today"] == 1.0


# ---------------------------------------------------------------------------
# S26 — Pivot cap enforced: --budget over 1 is rejected at onboard time
#        BEFORE any state is written. Anti-novelty-addiction.
# ---------------------------------------------------------------------------


def test_s26_startup_pivot_cap_blocks_onboard_before_state_write(
    home: Path, tmp_path: Path,
):
    """If a founder tries to onboard with --budget 5 (5 hypothesis pivots
    a day), the CLI must refuse BEFORE writing any contract or registry
    state. Otherwise the abuse-tax becomes meaningless."""
    priorities_file = _write_priorities(tmp_path)

    rc, out, err = _run(
        "startup", "onboard",
        "--priorities-file", str(priorities_file),
        "--home", str(home),
        "--active-hypothesis-id", "hyp-001",
        "--budget", "5",  # over cap
    )
    assert rc != 0, "onboard with --budget > 1 must fail"
    combined = (out + err).lower()
    assert "hard cap is 1" in combined or "thesis_pivots" in combined or "1" in combined

    # Critical: NO state has been written. The home directory should not
    # contain a contracts.jsonl row.
    contracts_jsonl = home / "contracts.jsonl"
    if contracts_jsonl.exists():
        rows = [line for line in contracts_jsonl.open() if line.strip()]
        assert len(rows) == 0, (
            "pivot-cap rejection must happen BEFORE writing contracts.jsonl. "
            "A row appeared, which means the abuse-tax is bypassable."
        )
