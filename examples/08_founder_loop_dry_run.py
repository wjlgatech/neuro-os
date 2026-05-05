"""
Dry-run the daily founder_loop against a synthetic 24h fixture.

Use:
    python examples/08_founder_loop_dry_run.py

What it does:
  1. Builds a synthetic 24h workflowx fixture that walks through a
     plausible day: morning deep work, mid-morning novelty hunger,
     afternoon fade, post-meal uptick, evening ration unlock.
  2. Binds a contract with three priorities.
  3. Stubs the predictor with deterministic forecasts that match each
     hour's narrative.
  4. Runs ``loop.tick()`` for each hour, building a 24-row registry.
  5. Calls ``loop.nightly()`` and prints the MAE + contract-honor +
     goldens summary.

No API key needed. Demonstrates the full data path.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.founder_loop import FounderLoop, Priority
from agent.founder_loop.observe import RawEvent
from agent.founder_loop.predict import set_predict_fn
from agent.founder_loop.state import ForecastedState


def _write_fixture(path: Path) -> None:
    """A 24h synthetic workflowx export."""
    base = datetime(2026, 5, 5, 0, tzinfo=timezone.utc)
    events = []
    for h in range(24):
        ts = base + timedelta(hours=h)
        # Simple narrative: morning productive, lunch dip, afternoon fade,
        # evening recovery.
        if 9 <= h <= 11:
            distraction, deep = 5.0, 50.0
            intent = "deep work on founder_loop"
        elif h == 12:
            distraction, deep = 30.0, 5.0
            intent = "lunch / context switch"
        elif 13 <= h <= 14:
            distraction, deep = 12.0, 35.0
            intent = "afternoon coding"
        elif h == 15:
            distraction, deep = 45.0, 8.0
            intent = "tired, scrolling"
        elif 16 <= h <= 17:
            distraction, deep = 10.0, 30.0
            intent = "after-coffee push"
        elif 18 <= h <= 21:
            distraction, deep = 30.0, 5.0
            intent = "evening unwinding"
        else:
            distraction, deep = 0.0, 0.0
            intent = None
        events.append(RawEvent(
            timestamp=ts,
            distraction_minutes=distraction,
            deep_work_minutes=deep,
            context_switches=h % 5,
            sleep_last_night_hours=7.0 if h < 9 else None,
            time_since_last_meal_min=(h - 12) * 60 if 12 <= h <= 18 else None,
            last_intent=intent,
            day_kind="work",
        ))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(e.model_dump_json() + "\n")


def _stub_predictor():
    """Predict close-to-actual most of the time; deliberately miss at 3pm
    so the morning_overconfidence-equivalent fires for the user to see.
    """
    def fn(state, intent):
        h = state.timestamp.hour
        if h == 15:
            urge, need = "entertainment", "fatigue"
            failure = "youtube_drift"
        elif h in (10, 11):
            urge, need, failure = "novelty", "novelty_hunger", None
        elif h == 12:
            urge, need, failure = "none", "decision_fatigue", None
        else:
            urge, need, failure = "none", "none", None
        return ForecastedState(
            predicted_distraction_min=state.distraction_minutes_last_hour,
            predicted_deep_work_min=state.deep_work_minutes_last_hour,
            predicted_urge=urge,
            predicted_underlying_need=need,
            predicted_main_failure_mode=failure,
            confidence="medium",
            reasoning=f"hour {h} stub forecast",
        )
    set_predict_fn(fn)


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="founder_loop_dry_"))
    fixture = workdir / "workflowx_export.jsonl"
    registry = workdir / "registry.jsonl"
    contracts = workdir / "contracts.jsonl"
    print(f"workdir: {workdir}\n")

    _write_fixture(fixture)
    _stub_predictor()

    loop = FounderLoop(
        registry_path=registry,
        contract_path=contracts,
        workflowx_export_path=fixture,
    )
    contract = loop.morning_ritual(
        priorities=[
            Priority(title="ship founder_loop v0", evidence_type="pr_merged",
                     evidence_target="#143", weight=3),
            Priority(title="2 commits on tests", evidence_type="commit_pushed",
                     evidence_target="2_commits", weight=2),
            Priority(title="afternoon walk", evidence_type="count_reached",
                     evidence_target="1", weight=1),
        ],
        entertainment_ration_min=60,
    )
    print("Bound contract:")
    print(json.dumps(json.loads(contract.model_dump_json()), indent=2)[:600])
    print("\n--- 24 ticks ---\n")

    base = datetime(2026, 5, 5, 0, tzinfo=timezone.utc)
    for h in range(24):
        now = base + timedelta(hours=h)
        result = loop.tick(now=now)
        print(f"  h={h:02d} | op={result.action.op:<35} | "
              f"need={(result.action.diagnosis.underlying_need if result.action.diagnosis else '-'):<18} | "
              f"tank={result.tank.percent:5.1f}% | "
              f"contract={'OK' if result.action.contract_check.honored else 'VIOLATION'}")

    print("\n--- nightly summary ---\n")
    summary = loop.nightly(day=base + timedelta(hours=23))
    print(json.dumps(json.loads(summary.model_dump_json()), indent=2))

    print(f"\nartifacts at: {workdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
