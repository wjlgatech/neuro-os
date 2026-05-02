"""End-to-end test for the self-evolving loop."""
import json
import unittest
from pathlib import Path

from agent import primitive_feedback, version_registry
from agent.self_evolving_loop import run_self_evolution


class TestSelfEvolvingLoop(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(self._tmp_dir_for_test())
        version_registry.set_registry_path(self.tmp_dir / "version_registry.jsonl")
        primitive_feedback.FEEDBACK_PATH = self.tmp_dir / "primitive_feedback.jsonl"
        primitive_feedback.reset_for_tests()

    def _tmp_dir_for_test(self):
        import tempfile
        return tempfile.mkdtemp(prefix="neuro_loop_test_")

    def test_loop_writes_registry_and_classifies_known_mechanisms(self):
        docs = [
            "Predictive coding minimizes sensory prediction error.",
            "Dopamine neurons encode reward prediction error.",
            "This sentence has no neuroscience signal.",
        ]
        report = run_self_evolution(docs)
        # one ingest + one registry entry per doc
        self.assertEqual(len(report["ingested"]), 3)
        self.assertEqual(len(report["registry_entries"]), 3)
        # registry was actually written to disk
        self.assertTrue((self.tmp_dir / "version_registry.jsonl").exists())
        on_disk = [
            json.loads(line)
            for line in (self.tmp_dir / "version_registry.jsonl").read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual(len(on_disk), 3)
        mechanisms = [e["mechanism"] for e in on_disk]
        self.assertIn("predictive_processing", mechanisms)
        self.assertIn("reinforcement_learning", mechanisms)
        self.assertIn("unknown", mechanisms)

    def test_loop_in_sandbox_runs_import_smoke_test(self):
        report = run_self_evolution(
            ["Predictive coding minimizes prediction error."],
            run_in_sandbox=True,
        )
        self.assertIsNotNone(report["sandbox"])
        self.assertTrue(report["sandbox"]["success"])


if __name__ == "__main__":
    unittest.main()
