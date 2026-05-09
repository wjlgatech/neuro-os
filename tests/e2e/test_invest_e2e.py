"""
End-to-end CLI scenarios for the **investment** vertical.

⚠️ Investment v0 is **advisory-only**. The load-bearing assertion
across every step is that the `advisory_only=True` flag survives
end-to-end, from contract → tick → nightly. If a future change
ever wires this vertical to a broker, these tests fail.

Catalog: scenarios.md S23 (full-day flow), S24 (advisory-only invariant).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def home(tmp_path) -> Path:
    return tmp_path / "invest_home"


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
            "title": "document AAPL services-revenue thesis",
            "evidence_type": "thesis_documented",
            "evidence_target": "PositionThesis for AAPL",
            "weight": 2,
            "instrument": "AAPL",
        },
    ]))
    return f


# ---------------------------------------------------------------------------
# S23 — Investor's full day: onboard → narrative-following tick →
#       price-obsessed tick → nightly. Two propose actions, no overrides.
# ---------------------------------------------------------------------------


def test_s23_invest_full_day_flow(home: Path, tmp_path: Path):
    priorities_file = _write_priorities(tmp_path)

    # --- morning: onboard, advisory-only flag is set on contract -------
    rc, out, err = _run(
        "invest", "onboard",
        "--priorities-file", str(priorities_file),
        "--home", str(home),
    )
    assert rc == 0, err
    contract = json.loads(out)
    assert contract["advisory_only"] is True, (
        "investment contract must carry advisory_only=True from morning_ritual"
    )
    assert len(contract["priorities"]) == 1

    # --- midday: caught FOMO-ing on a narrative -----------------------
    rc, out, err = _run(
        "invest", "tick",
        "--drift", "narrative_following",
        "--home", str(home),
    )
    assert rc == 0, err
    narrative = json.loads(out)
    assert narrative["action"]["op"] == "propose_constructive_expression"
    # advisory_only also rides on the action payload, the way Founder OS
    # downstream consumers would see it.
    assert narrative["action"]["payload"]["advisory_only"] is True

    # --- afternoon: caught refreshing the chart ----------------------
    rc, out, err = _run(
        "invest", "tick",
        "--drift", "price_obsessed",
        "--home", str(home),
    )
    assert rc == 0, err
    price = json.loads(out)
    assert price["action"]["payload"]["advisory_only"] is True

    # --- registry has both rows --------------------------------------
    registry_jsonl = home / "registry.jsonl"
    assert registry_jsonl.exists()
    rows = [json.loads(line) for line in registry_jsonl.open() if line.strip()]
    assert len(rows) == 2
    # Every row's action carries advisory_only=True in its payload.
    for r in rows:
        assert r["action"]["payload"]["advisory_only"] is True

    # --- evening: nightly summary -------------------------------------
    rc, out, err = _run(
        "invest", "nightly",
        "--home", str(home),
    )
    assert rc == 0, err
    summary = json.loads(out)
    assert summary["vertical"] == "investment"
    assert summary["primary_metric_label"] == "calibration error"
    assert summary["primary_resource_label"] == "position edits"
    # 2 non-continue actions today.
    assert summary["primary_resource_used_today"] == 2.0
    # advisory_only flag is in extras — the load-bearing invariant.
    assert summary["extra"]["advisory_only"] is True


# ---------------------------------------------------------------------------
# S24 — Advisory-only invariant: NO action's payload ever lacks the flag,
#        across every drift mode.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("drift", [
    "emotional",
    "narrative_following",
    "price_obsessed",
    "overconfident",
    "social_proof_following",
    "ego_attached",
])
def test_s24_advisory_only_flag_present_for_every_drift_mode(
    home: Path, drift: str,
):
    """For every one of investment's 6 named drift modes, the resulting
    action payload must carry advisory_only=True. This is the test that
    fires CI red if anyone later removes the flag from a drift branch."""
    rc, out, err = _run(
        "invest", "tick",
        "--drift", drift,
        "--home", str(home),
        "--dry-run",
    )
    assert rc == 0, err
    result = json.loads(out)
    assert result["action"]["op"] == "propose_constructive_expression"
    assert result["action"]["payload"]["advisory_only"] is True, (
        f"drift={drift!r} produced an action without advisory_only=True. "
        f"Investment vertical must be advisory-only end-to-end."
    )
