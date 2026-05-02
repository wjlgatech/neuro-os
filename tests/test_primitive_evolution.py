import unittest

from agent.primitive_evolution_evaluator import evaluate_update_dict

class TestPrimitiveEvolution(unittest.TestCase):

    def test_strong_update_accept(self):
        data = {
            "primitive_name": "attention",
            "proposed_change": "Attention gates signals",
            "experience_probe": "Observe focus vs distraction",
            "experiment_design": "Compare recall",
            "failure_condition": "If outcome fails, reject",
            "one_sentence_definition": "Attention selects signals",
            "felt_sense_bridge": "Feels like narrowing",
            "immediate_use_case": "Use in next meeting",
            "repeat_protocol": "Repeat 3 times",
            "measurement": "Recall score",
            "refinement_signal": "If no gain, refine",
            "version_delta": "Added experiment",
            "transfer_domains": ["brain", "AI"],
            "transform_formats": ["sentence", "diagram", "practice"],
            "source_quote": "Attention routes signals",
            "source_type": "paper",
            "evidence_strength": "strong",
            "contradictions_or_limits": "Can miss weak signals",
            "changed_files": ["file.md"],
            "tests_pass": True,
            "rollback_available": True
        }
        result = evaluate_update_dict(data)
        self.assertIn(result["decision"], ["ACCEPT", "REFINE"])

    def test_missing_fields_fail(self):
        with self.assertRaises(ValueError):
            evaluate_update_dict({"primitive_name": "x"})

    def test_no_tests_reject(self):
        data = {
            "primitive_name": "attention",
            "proposed_change": "x",
            "experience_probe": "x",
            "experiment_design": "x",
            "failure_condition": "fail condition",
            "one_sentence_definition": "x",
            "felt_sense_bridge": "x",
            "immediate_use_case": "x",
            "repeat_protocol": "x",
            "measurement": "x",
            "refinement_signal": "x",
            "version_delta": "x",
            "transfer_domains": ["brain", "AI"],
            "transform_formats": ["a", "b", "c"],
            "source_quote": "x",
            "source_type": "paper",
            "evidence_strength": "weak",
            "contradictions_or_limits": "x",
            "changed_files": ["x"],
            "tests_pass": False,
            "rollback_available": True
        }
        result = evaluate_update_dict(data)
        self.assertEqual(result["decision"], "REJECT")

if __name__ == "__main__":
    unittest.main()
