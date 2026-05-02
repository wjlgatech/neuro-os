import unittest

from agent.self_evolution_controller import (
    GOLDEN_CASES,
    observe,
    evaluate_observations,
    propose_controls,
    validate_change,
    run_self_evolution,
)
from agent.ingestion_pipeline import run_pipeline


class TestTRUEPipeline(unittest.TestCase):
    def test_golden_cases_classify_correctly(self):
        observations = observe(GOLDEN_CASES, pipeline_fn=lambda t: run_pipeline(t))
        for obs in observations:
            self.assertEqual(obs.actual_mechanism, obs.expected_mechanism)
            self.assertEqual(obs.decision, "ACCEPT")

    def test_unknown_rejects(self):
        result = run_pipeline("This sentence has no neuroscience signal.")
        self.assertEqual(result["decision"], "REJECT")


class TestSelfEvolutionController(unittest.TestCase):
    def test_observe_and_evaluate(self):
        observations = observe(GOLDEN_CASES, pipeline_fn=lambda t: run_pipeline(t))
        report = evaluate_observations(observations)
        self.assertEqual(report.total, len(GOLDEN_CASES))
        self.assertGreaterEqual(report.accuracy, 1.0)

    def test_proposes_control_for_reward_prediction_error_misclassification(self):
        # Fake a bad pipeline that misclassifies RL as predictive_processing
        def bad_pipeline(text):
            result = run_pipeline(text)
            if "reward prediction error" in text.lower():
                result["knowledge"]["mechanism"] = "predictive_processing"
            return result

        observations = observe(GOLDEN_CASES, pipeline_fn=bad_pipeline)
        report = evaluate_observations(observations)
        proposals = propose_controls(report)
        ids = [p.change_id for p in proposals]
        self.assertIn("prioritize_reward_prediction_error", ids)

    def test_validate_change_accepts_beneficial_change(self):
        before = evaluate_observations(observe(GOLDEN_CASES, pipeline_fn=lambda t: run_pipeline(t)))

        # Simulate improvement: same as before (already optimal)
        after = evaluate_observations(observe(GOLDEN_CASES, pipeline_fn=lambda t: run_pipeline(t)))

        validation = validate_change(before, after)
        self.assertTrue(validation.beneficial)

    def test_self_evolution_stable_when_all_golden_cases_pass(self):
        result = run_self_evolution(pipeline_fn=lambda t: run_pipeline(t))
        self.assertEqual(result["status"], "STABLE")


if __name__ == "__main__":
    unittest.main()
