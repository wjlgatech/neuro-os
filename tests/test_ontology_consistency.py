import unittest

from agent.ontology_consistency import check_extraction_consistency


class TestOntologyConsistency(unittest.TestCase):

    def test_pass_basic(self):
        ontology = {
            "primitives": {
                "attention": {
                    "definition": "Attention gates signals.",
                    "relations": []
                }
            }
        }
        extracted = {
            "mechanism": "attention",
            "core_mechanism": "Attention gates signals",
            "main_claim": "Attention gates signals",
            "connection_to_ai": "transformer attention",
            "connection_to_human_thinking": "focus",
        }
        result = check_extraction_consistency(extracted, ontology)
        self.assertIn(result["decision"], ["PASS", "REFINE"])  # no contradictions

    def test_reject_contradiction(self):
        ontology = {
            "primitives": {
                "attention": {
                    "definition": "Attention gates signals.",
                    "relations": []
                }
            }
        }
        extracted = {
            "mechanism": "attention",
            "core_mechanism": "Attention does not gate signals",
            "main_claim": "Attention does not gate signals",
            "connection_to_ai": "transformer attention",
            "connection_to_human_thinking": "focus",
        }
        result = check_extraction_consistency(extracted, ontology)
        self.assertEqual(result["decision"], "REJECT")

    def test_unknown_reject(self):
        ontology = {"primitives": {}}
        extracted = {"mechanism": "unknown"}
        result = check_extraction_consistency(extracted, ontology)
        self.assertEqual(result["decision"], "REJECT")


if __name__ == "__main__":
    unittest.main()
