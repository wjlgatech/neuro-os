import unittest

from agent.ontology_evolution import evolve_from_extraction


class TestOntologyEvolution(unittest.TestCase):

    def test_no_action_when_consistent(self):
        ontology = {
            "primitives": {
                "attention": {"definition": "Attention gates signals.", "relations": []}
            }
        }
        pipeline_result = {
            "knowledge": {
                "mechanism": "attention",
                "core_mechanism": "Attention gates signals",
                "main_claim": "Attention gates signals",
                "connection_to_human_thinking": "focus",
                "evidence_quotes": ["Attention gates signals"],
                "source_type": "paper",
            },
            "true_validation": {"scores": {"TRUE": 0.9}},
        }
        result = evolve_from_extraction(pipeline_result, ontology)
        self.assertEqual(result["action"], "NO_ACTION")

    def test_propose_refinement_on_contradiction(self):
        ontology = {
            "primitives": {
                "attention": {"definition": "Attention gates signals.", "relations": []}
            }
        }
        pipeline_result = {
            "knowledge": {
                "mechanism": "attention",
                "core_mechanism": "Attention does not gate signals",
                "main_claim": "Attention does not gate signals",
                "connection_to_human_thinking": "focus",
                "evidence_quotes": ["Attention does not gate signals"],
                "source_type": "paper",
            },
            "true_validation": {"scores": {"TRUE": 0.8}},
        }
        result = evolve_from_extraction(pipeline_result, ontology)
        self.assertIn(result["action"], ["PROPOSE_REFINEMENT", "ESCALATE_REVIEW"])
        self.assertIsNotNone(result["proposal"])


if __name__ == "__main__":
    unittest.main()
