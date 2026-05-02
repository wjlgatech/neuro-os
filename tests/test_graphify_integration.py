"""Tests for the graphify -> neuro-os bridge."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from agent.integrations.graphify import (
    confidence_to_evidence_strength,
    graphify_node_to_text,
    load_graph,
    process_graphify_graph,
)


FIXTURE = Path(__file__).parent / "fixtures" / "graphify_sample.json"


class TestConfidenceMapping(unittest.TestCase):
    def test_extracted_yields_strong(self):
        self.assertEqual(confidence_to_evidence_strength(["EXTRACTED"]), "strong")

    def test_inferred_yields_moderate(self):
        self.assertEqual(confidence_to_evidence_strength(["INFERRED"]), "moderate")

    def test_ambiguous_yields_weak(self):
        self.assertEqual(confidence_to_evidence_strength(["AMBIGUOUS"]), "weak")

    def test_takes_strongest_label(self):
        # Mixed labels: the strongest wins.
        self.assertEqual(
            confidence_to_evidence_strength(["AMBIGUOUS", "INFERRED", "EXTRACTED"]),
            "strong",
        )

    def test_empty_yields_weak(self):
        self.assertEqual(confidence_to_evidence_strength([]), "weak")
        self.assertEqual(confidence_to_evidence_strength([None]), "weak")


class TestNodeToText(unittest.TestCase):
    def setUp(self):
        self.graph = load_graph(FIXTURE)
        self.by_id = {n["id"]: n for n in self.graph["nodes"]}

    def test_includes_label_and_file_type(self):
        text = graphify_node_to_text(self.by_id["predictive_coding"], self.graph)
        self.assertIn("predictive coding", text)
        self.assertIn("doc", text)

    def test_includes_neighbor_relations(self):
        text = graphify_node_to_text(self.by_id["predictive_coding"], self.graph)
        # predictive_coding has 3 incoming edges (rl_dopamine, attention_qkv, hebbian_stdp)
        self.assertIn("from", text.lower())


class TestProcessGraphifyGraph(unittest.TestCase):
    def test_pipeline_classifies_known_neuroscience_nodes(self):
        report = process_graphify_graph(FIXTURE)
        self.assertEqual(report["node_count"], 5)
        self.assertEqual(report["processed"], 5)
        # Build a label -> mechanism mapping so we can assert per-node.
        by_label = {r["label"]: r["neuro_os_mechanism"] for r in report["results"]}
        self.assertEqual(by_label["dopamine reward prediction error"], "reinforcement_learning")
        self.assertEqual(by_label["predictive coding cortical hierarchy"], "predictive_processing")
        self.assertEqual(by_label["attention query key value gating"], "attention")
        self.assertEqual(by_label["hebbian fire together wire together"], "hebbian_learning")
        # Noise node should not classify into any neuroscience primitive.
        self.assertEqual(by_label["miscellaneous review note"], "unknown")

    def test_evidence_strength_is_aggregated_from_graphify_confidences(self):
        report = process_graphify_graph(FIXTURE)
        by_id = {r["node_id"]: r for r in report["results"]}
        # rl_dopamine has at least one EXTRACTED edge → strong
        self.assertEqual(by_id["rl_dopamine"]["graphify_evidence_strength"], "strong")
        # noise_node has no edges → weak
        self.assertEqual(by_id["noise_node"]["graphify_evidence_strength"], "weak")

    def test_summary_decision_histogram(self):
        report = process_graphify_graph(FIXTURE)
        decisions = report["summary"]["decisions"]
        # 4 known neuroscience nodes should ACCEPT, 1 noise node should REJECT.
        self.assertEqual(decisions.get("ACCEPT", 0), 4)
        self.assertEqual(decisions.get("REJECT", 0), 1)

    def test_max_nodes_caps_processing(self):
        report = process_graphify_graph(FIXTURE, max_nodes=2)
        self.assertEqual(report["processed"], 2)

    def test_min_incoming_edges_filters_noise(self):
        # noise_node has zero incoming edges; with min_incoming_edges=1 it's skipped.
        report = process_graphify_graph(FIXTURE, min_incoming_edges=1)
        labels = [r["label"] for r in report["results"]]
        self.assertNotIn("miscellaneous review note", labels)


class TestLoadGraph(unittest.TestCase):
    def test_rejects_non_graph_json(self, tmp_path=None):
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"foo": "bar"}, f)
            tmp_path = f.name
        with self.assertRaises(ValueError):
            load_graph(tmp_path)


if __name__ == "__main__":
    unittest.main()
