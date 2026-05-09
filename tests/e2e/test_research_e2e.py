"""
End-to-end CLI scenarios for the **research** vertical.

Drives `neuro-os research {onboard,tick,nightly}` as subprocess
calls and asserts that state persists across commands via the
registry / contracts files written under ``--home``. This is
distinct from ``tests/test_verticals_cli.py``, which exercises each
subcommand in isolation; here the focus is multi-step user
journeys.

Catalog: scenarios.md S21 (research full-day flow).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def home(tmp_path) -> Path:
    return tmp_path / "research_home"


def _run(*args: str) -> tuple[int, str, str]:
    """Run `python -m agent <args>` and return (rc, stdout, stderr)."""
    p = subprocess.run(
        [sys.executable, "-m", "agent", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return p.returncode, p.stdout, p.stderr


def _write_priorities(tmp_path: Path) -> Path:
    """A small priorities file pointing at thesis-001."""
    f = tmp_path / "priorities.json"
    f.write_text(json.dumps([
        {
            "title": "extract one MechanismCard from Friston 2010",
            "evidence_type": "paper_read",
            "evidence_target": "MechanismCard for predictive coding",
            "weight": 3,
            "thesis_id": "thesis-001",
        },
    ]))
    return f


# ---------------------------------------------------------------------------
# S21 — Researcher's full day: onboard → drift tick → continue tick → nightly
# ---------------------------------------------------------------------------


def test_s21_research_full_day_flow(home: Path, tmp_path: Path):
    """
    A researcher onboards in the morning, has a paper-collector drift
    moment at noon (logged via `tick --drift`), works clean for the
    rest of the day (a continue tick), and pulls up the nightly
    summary at the end of day. Verifies:

    * contract is signed and reachable on disk
    * tick writes a registry row (no --dry-run)
    * nightly aggregates today's rows into the 4 first-class metrics
    * vertical-specific extras (continuity hint) are present
    """
    priorities_file = _write_priorities(tmp_path)

    # --- morning: onboard ------------------------------------------------
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

    contracts_jsonl = home / "contracts.jsonl"
    assert contracts_jsonl.exists(), \
        "onboard must persist the contract under --home/contracts.jsonl"
    assert sum(1 for _ in contracts_jsonl.open()) == 1

    # --- noon: drift tick ------------------------------------------------
    # NB: NO --dry-run, so this tick writes a row to the registry.
    rc, out, err = _run(
        "research", "tick",
        "--drift", "paper_collector",
        "--home", str(home),
    )
    assert rc == 0, err
    drift_result = json.loads(out)
    assert drift_result["action"]["op"] == "propose_constructive_expression"
    assert drift_result["action"]["diagnosis"]["underlying_need"] == "paper_collector"

    # --- afternoon: clean tick (no drift) -------------------------------
    rc, out, err = _run(
        "research", "tick",
        "--home", str(home),
    )
    assert rc == 0, err
    clean_result = json.loads(out)
    assert clean_result["action"]["op"] == "continue"

    # --- registry has both rows -----------------------------------------
    registry_jsonl = home / "registry.jsonl"
    assert registry_jsonl.exists()
    rows = [json.loads(line) for line in registry_jsonl.open() if line.strip()]
    assert len(rows) == 2
    assert {r["action"]["op"] for r in rows} == {
        "propose_constructive_expression", "continue",
    }

    # --- evening: nightly summary ---------------------------------------
    rc, out, err = _run(
        "research", "nightly",
        "--home", str(home),
    )
    assert rc == 0, err
    summary = json.loads(out)
    assert summary["vertical"] == "research"
    assert summary["primary_metric_label"] == "mechanism cards/day"
    assert summary["primary_resource_label"] == "papers read"
    # Both ticks honored the contract (continue + propose) → honor rate 1.0.
    assert summary["honor_rate_today"] == 1.0
    # Sublimation success rate: the one propose op had no later violation.
    assert summary["primary_success_rate_today"] == 1.0
    # Vertical-specific signal lives under `extra`.
    assert "thesis_continuity_check" in summary["extra"]


# ---------------------------------------------------------------------------
# S22 — Single-thesis discipline: tick survives without `--active-thesis-id`
#        on subsequent ticks (state persisted from onboard)
# ---------------------------------------------------------------------------


def test_s22_research_tick_does_not_require_thesis_id_after_onboard(
    home: Path, tmp_path: Path,
):
    """
    Onboard binds the active thesis. Subsequent ticks should not need
    the user to re-name it — that's the whole point of "sign once,
    work all day." This test fails if a future change inadvertently
    requires `--active-thesis-id` on every tick.
    """
    priorities_file = _write_priorities(tmp_path)
    rc, _, err = _run(
        "research", "onboard",
        "--priorities-file", str(priorities_file),
        "--home", str(home),
        "--active-thesis-id", "thesis-001",
    )
    assert rc == 0, err

    # No --active-thesis-id on the tick. Should still succeed.
    rc, out, err = _run(
        "research", "tick",
        "--drift", "topic_hopper",
        "--home", str(home),
        "--dry-run",
    )
    assert rc == 0, err
    result = json.loads(out)
    assert result["action"]["diagnosis"]["underlying_need"] == "topic_hopper"
