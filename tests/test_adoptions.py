"""Tests for the four ChatGPT-driven adoptions:

1. real evidence-strength heuristic
2. ontology auto-merge with learn-back
3. golden-case gate before merge
4. process_text + CLI surface
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from agent import primitive_feedback, version_registry
from agent.api import ingest_documents, process_text
from agent.cli import main as cli_main
from agent.ingestion_pipeline import classify_evidence_strength
from agent.self_evolving_loop import (
    _apply_ontology_merge,
    _golden_accuracy,
    _revert_ontology_merge,
    run_self_evolution,
)


class _PersistedFilesMixin:
    """Reset registry + feedback to a fresh tempdir per test."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="neuro_adopt_test_"))
        version_registry.set_registry_path(self.tmp_dir / "version_registry.jsonl")
        primitive_feedback.FEEDBACK_PATH = self.tmp_dir / "primitive_feedback.jsonl"
        primitive_feedback.reset_for_tests()


class TestEvidenceHeuristic(unittest.TestCase):
    def test_weak_when_no_markers(self):
        self.assertEqual(classify_evidence_strength("just some plain words"), "weak")
        self.assertEqual(classify_evidence_strength(""), "weak")

    def test_moderate_with_single_marker(self):
        self.assertEqual(
            classify_evidence_strength("see https://example.com/paper"),
            "moderate",
        )

    def test_strong_with_year_author_and_doi(self):
        text = "Friston et al. (2010) https://doi.org/10.1234/abc.5678"
        self.assertEqual(classify_evidence_strength(text), "strong")

    def test_strong_with_doi_and_url(self):
        text = "https://example.org doi 10.1000/xyz123"
        # doi 10.1000/xyz123 matches the DOI regex; URL adds a second marker.
        self.assertEqual(classify_evidence_strength(text), "strong")


class TestOntologyMergePrimitives(unittest.TestCase):
    def setUp(self):
        self.ontology = {
            "primitives": {
                "attention": {
                    "definition": "Attention selectively gates which signals control processing.",
                    "aliases": ["attention"],
                    "sources": [],
                    "relations": [],
                }
            }
        }
        self.proposal = {
            "primitive_name": "attention",
            "one_sentence_definition": "Attention is best modeled as precision-weighted gating.",
            "source_quote": "Friston (2010) doi:10.1234/abc.5678",
        }

    def test_apply_merge_updates_definition_and_records_source(self):
        snapshot = _apply_ontology_merge(self.ontology, self.proposal)
        self.assertEqual(
            self.ontology["primitives"]["attention"]["definition"],
            "Attention is best modeled as precision-weighted gating.",
        )
        self.assertIn(
            "Friston (2010) doi:10.1234/abc.5678",
            self.ontology["primitives"]["attention"]["sources"],
        )
        self.assertEqual(snapshot["definition"], "Attention selectively gates which signals control processing.")

    def test_revert_restores_snapshot(self):
        snapshot = _apply_ontology_merge(self.ontology, self.proposal)
        _revert_ontology_merge(self.ontology, "attention", snapshot)
        self.assertEqual(
            self.ontology["primitives"]["attention"]["definition"],
            "Attention selectively gates which signals control processing.",
        )
        self.assertEqual(self.ontology["primitives"]["attention"]["sources"], [])


class TestGoldenGate(_PersistedFilesMixin, unittest.TestCase):
    def test_golden_accuracy_on_canonical_ontology_is_perfect(self):
        from agent.ingestion_pipeline import _canonical_ontology
        self.assertEqual(_golden_accuracy(_canonical_ontology()), 1.0)

    def test_loop_reverts_merge_when_goldens_regress(self):
        # Force a regression: monkey-patch _golden_accuracy so the
        # post-merge accuracy is lower than the baseline.
        accuracies = iter([1.0, 0.5])
        with mock.patch(
            "agent.self_evolving_loop._golden_accuracy",
            side_effect=lambda *a, **kw: next(accuracies),
        ):
            citation = (
                "Vaswani et al. (2017) https://doi.org/10.1234/qkv attention does not gate signals."
            )
            report = run_self_evolution([citation])

        self.assertEqual(report["merges_applied"], 0)
        self.assertEqual(report["merges_reverted"], 1)
        # Registry entry recorded the rollback
        entry = report["registry_entries"][-1]
        self.assertEqual(entry["merge_status"], "reverted_on_regression")
        self.assertEqual(entry["golden_accuracy_before"], 1.0)
        self.assertEqual(entry["golden_accuracy_after"], 0.5)
        # Feedback file did not record the reverted update
        self.assertFalse(primitive_feedback.FEEDBACK_PATH.exists())


class TestLearnBackEndToEnd(_PersistedFilesMixin, unittest.TestCase):
    def test_accepted_refinement_persists_to_ontology_file(self):
        ontology_path = self.tmp_dir / "ontology.json"
        # Citation-rich contradiction → strong evidence → ACCEPT path.
        contradiction = (
            "Vaswani et al. (2017) https://doi.org/10.1234/qkv claims attention "
            "does not gate signals — see arXiv:1706.03762."
        )

        report = ingest_documents([contradiction], ontology_path=ontology_path)

        # First-pass: evolution proposed a refinement and the merge applied.
        self.assertGreaterEqual(report["merges_applied"], 1)
        self.assertTrue(ontology_path.exists())
        on_disk = json.loads(ontology_path.read_text())
        new_def = on_disk["primitives"]["attention"]["definition"]
        self.assertNotEqual(
            new_def,
            "Attention selectively gates which signals control processing.",
        )
        # Source quote is recorded.
        self.assertTrue(on_disk["primitives"]["attention"]["sources"])

        # The system "learned": build_extraction_context now surfaces the new
        # definition for downstream extraction prompts.
        ctx = primitive_feedback.build_extraction_context()
        self.assertIn("attention", ctx["primitive_definitions"])


class TestProcessTextAndCli(_PersistedFilesMixin, unittest.TestCase):
    def test_process_text_returns_structured_result(self):
        result = process_text("Predictive coding minimizes sensory prediction error.")
        self.assertEqual(result["mechanism"], "predictive_processing")
        self.assertEqual(result["pipeline_decision"], "ACCEPT")
        self.assertEqual(result["action"], "NO_ACTION")
        self.assertIn("feedback_context", result)

    def test_cli_extract_emits_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main([
                "extract",
                "Dopamine neurons encode reward prediction error signals.",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["mechanism"], "reinforcement_learning")

    def test_cli_build_ontology_writes_file(self):
        src = self.tmp_dir / "src.txt"
        src.write_text(
            "## 1. PREDICTIVE PROCESSING\n"
            "### Papers\n"
            "- **Friston 2010**\n"
            "Key idea: Brain minimizes prediction error.\n"
        )
        out = self.tmp_dir / "ont.json"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main(["build-ontology", str(src), str(out)])
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())
        on_disk = json.loads(out.read_text())
        self.assertIn("predictive_processing", on_disk["primitives"])

    def test_cli_ingest_drives_loop(self):
        ontology_out = self.tmp_dir / "updated.json"
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main([
                "ingest",
                "Predictive coding minimizes prediction error.",
                "--ontology-out",
                str(ontology_out),
            ])
        self.assertEqual(rc, 0)
        report = json.loads(buf.getvalue())
        self.assertEqual(len(report["registry_entries"]), 1)


if __name__ == "__main__":
    unittest.main()
