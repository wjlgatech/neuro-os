import unittest
from agent.ontology_builder import parse_source_index

class TestOntologyBuilder(unittest.TestCase):

    def test_parse_basic(self):
        text = """
## 1. PREDICTIVE PROCESSING
### Papers
- **Test Paper**
URL: http://example.com
Key idea: Brain predicts input
"""
        ontology = parse_source_index(text)
        self.assertGreaterEqual(ontology["source_count"], 1)
        self.assertIn("predictive_processing", ontology["primitives"])

    def test_relations_exist(self):
        ontology = parse_source_index("## 1. PREDICTIVE PROCESSING")
        self.assertGreater(ontology["relation_count"], 0)

if __name__ == "__main__":
    unittest.main()
