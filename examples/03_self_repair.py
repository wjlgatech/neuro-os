"""
Example 03 — Watch neuro-os repair itself.

Removes every reinforcement-learning cue from the live priority-rules
data file, runs the closed self-modification loop, and watches it
detect the regression, propose an allowlisted patch, validate it in a
sandbox subprocess, and promote the patch back to the live tree.

The original file is restored on exit. Nothing else on disk is touched
beyond ``versions/`` and ``memory/`` (the registry / feedback logs).

Run::

    python examples/03_self_repair.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.domains import get_domain  # noqa: E402
from agent.ingestion_pipeline import PRIORITY_RULES_PATH, run_pipeline  # noqa: E402
from agent.self_modification import run_self_modification  # noqa: E402


GOLDEN = "Dopamine neurons encode reward prediction error signals."


def main() -> None:
    snapshot = PRIORITY_RULES_PATH.read_text(encoding="utf-8")

    try:
        # 1. Degrade the rules: drop every RL cue.
        rules = json.loads(snapshot)
        degraded = [r for r in rules if r[1] != "reinforcement_learning"]
        PRIORITY_RULES_PATH.write_text(
            json.dumps(degraded, indent=2) + "\n",
            encoding="utf-8",
        )

        before = run_pipeline(GOLDEN)["knowledge"]["mechanism"]
        print(f"before self-repair: pipeline classifies the dopamine golden as {before!r}")

        # 2. Run the meta loop.
        report = run_self_modification(get_domain("neuro_os_self_v1"))
        print(f"loop status:        {report['status']}")
        baseline_acc = report.get("baseline", {}).get("accuracy")
        if report["results"]:
            outcome = report["results"][0]
            print(f"  patch:            {outcome['patch']['op']} {outcome['patch']['payload']}")
            print(f"  baseline acc:     {baseline_acc}")
            print(f"  post-patch acc:   {outcome.get('post_accuracy')}")
            print(f"  promoted to live: {outcome.get('promote', {}).get('live_apply_success', False)}")

        # 3. Verify the live pipeline now classifies correctly.
        after = run_pipeline(GOLDEN)["knowledge"]["mechanism"]
        print(f"after self-repair:  pipeline classifies the dopamine golden as {after!r}")

    finally:
        PRIORITY_RULES_PATH.write_text(snapshot, encoding="utf-8")
        print("restored snapshot.")


if __name__ == "__main__":
    main()
