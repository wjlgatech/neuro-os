"""End-to-end test: a deliberately degraded priority rule is auto-repaired.

The test removes every reinforcement-learning cue from the live
``priority_rules.json``, then runs the self-modification loop. The
loop should observe a regression on the dopamine golden, propose a
patched control, validate it in a sandbox, and promote — restoring
the missing rule. The original file is restored on teardown.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from agent import primitive_feedback, version_registry
from agent.domains import get_domain
from agent.ingestion_pipeline import PRIORITY_RULES_PATH, get_priority_rules
from agent.patches import Patch, apply_patch
from agent.self_modification import run_self_modification


class TestSelfModification(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="neuro_selfmod_test_"))
        version_registry.set_registry_path(self.tmp_dir / "version_registry.jsonl")
        primitive_feedback.FEEDBACK_PATH = self.tmp_dir / "primitive_feedback.jsonl"
        primitive_feedback.reset_for_tests()

        # Snapshot the live priority rules so we can restore them in tearDown.
        self._original_rules_text = PRIORITY_RULES_PATH.read_text(encoding="utf-8")

        # Degrade: drop every reinforcement-learning cue. With these gone,
        # the dopamine golden ("Dopamine neurons encode reward prediction
        # error signals.") falls through to alias matching and is captured
        # by predictive_processing's "prediction error" alias first — a
        # real regression the loop must detect and repair.
        rules = json.loads(self._original_rules_text)
        degraded = [r for r in rules if r[1] != "reinforcement_learning"]
        PRIORITY_RULES_PATH.write_text(
            json.dumps(degraded, indent=2) + "\n",
            encoding="utf-8",
        )
        self.addCleanup(self._restore_rules)

    def _restore_rules(self):
        PRIORITY_RULES_PATH.write_text(self._original_rules_text, encoding="utf-8")

    def test_loop_repairs_missing_rl_priority_rule(self):
        # Sanity: the degraded state should misclassify the dopamine golden.
        from agent.ingestion_pipeline import run_pipeline
        result = run_pipeline(
            "Dopamine neurons encode reward prediction error signals."
        )
        self.assertNotEqual(
            result["knowledge"]["mechanism"],
            "reinforcement_learning",
            msg="precondition: degraded pipeline should misclassify",
        )

        # Run the meta loop against the self-as-domain.
        domain = get_domain("neuro_os_self_v1")
        report = run_self_modification(domain)

        self.assertEqual(report["status"], "MUTATION_PROMOTED", msg=report)
        self.assertEqual(report["patched_proposals"], 1)
        self.assertGreaterEqual(len(report["results"]), 1)
        outcome = report["results"][0]
        self.assertTrue(outcome["beneficial"])
        self.assertEqual(outcome["change_id"], "prioritize_reward_prediction_error")
        self.assertEqual(outcome["post_accuracy"], 1.0)

        # The live rule file should now contain the restored cue.
        rules_after = get_priority_rules()
        self.assertIn(
            ("reward prediction error", "reinforcement_learning"),
            rules_after,
            msg=f"rule was not restored: {rules_after}",
        )

        # Live pipeline should now classify the dopamine golden correctly.
        result_after = run_pipeline(
            "Dopamine neurons encode reward prediction error signals."
        )
        self.assertEqual(result_after["knowledge"]["mechanism"], "reinforcement_learning")

        # Registry recorded the mutation with provenance.
        registry_lines = [
            json.loads(line)
            for line in (self.tmp_dir / "version_registry.jsonl").read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual(len(registry_lines), 1)
        entry = registry_lines[0]
        self.assertEqual(entry["event"], "self_modification")
        self.assertEqual(entry["status"], "promoted")
        self.assertEqual(entry["change_id"], "prioritize_reward_prediction_error")
        self.assertEqual(entry["patch"]["op"], "append_priority_rule")
        self.assertEqual(entry["rollback_patch"]["op"], "remove_priority_rule")

    def test_patch_op_refuses_paths_outside_allowlist(self):
        patch = Patch(
            op="append_priority_rule",
            payload={"cue": "x", "mechanism": "reinforcement_learning"},
            target_path="agent/sandbox_runner.py",  # not on the allowlist
            description="malicious target",
        )
        domain = get_domain("neuro_os_self_v1")
        result = apply_patch(patch, ".", domain.mutable_paths)
        self.assertFalse(result.success)
        self.assertIn("not in mutable_paths", result.reason)

    def test_unknown_op_is_refused(self):
        patch = Patch(
            op="exec_arbitrary_python",
            payload={},
            target_path="agent/data/priority_rules.json",
        )
        domain = get_domain("neuro_os_self_v1")
        result = apply_patch(patch, ".", domain.mutable_paths)
        self.assertFalse(result.success)
        self.assertIn("ALLOWED_OPS", result.reason)

    def test_stable_domain_short_circuits(self):
        # With the rules restored to canonical state, the domain is stable
        # and the loop should report STABLE without proposing patches.
        self._restore_rules()
        domain = get_domain("neuro_os_self_v1")
        report = run_self_modification(domain)
        self.assertEqual(report["status"], "STABLE")
        self.assertEqual(report["patched_proposals"], 0)


if __name__ == "__main__":
    unittest.main()
