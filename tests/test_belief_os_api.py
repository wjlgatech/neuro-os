"""Tests for the public Belief-OS consumption surface (``agent.belief_os``).

These tests pin the *contract* that company-os Founder OS, money-os, and
any future research-os will rely on. Breaking changes here ripple
across the ecosystem, so this file is intentionally thorough about
return-shape stability.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent import primitive_feedback, version_registry
from agent.belief_os import (
    BeliefOS,
    BeliefRecord,
    ClassificationResult,
    DecisionCheckResult,
    FAILURE_MODE_PRIMITIVES,
    IngestResult,
    KNOWN_PRIMITIVES,
    SOUND_REASONING_PRIMITIVES,
    check_decision_text,
    classify_belief,
)


class TestPublicConstants(unittest.TestCase):
    """The exported constants are part of the public contract — pin them."""

    def test_known_primitives_lists_six_plus_unknown(self):
        self.assertIn("unknown", KNOWN_PRIMITIVES)
        self.assertEqual(len(KNOWN_PRIMITIVES), 7)
        for p in (
            "bayesian_updating",
            "base_rate_reasoning",
            "falsifiability",
            "expected_value",
            "second_order_thinking",
            "survivorship_bias",
        ):
            self.assertIn(p, KNOWN_PRIMITIVES)

    def test_failure_and_sound_partitions_are_disjoint(self):
        self.assertEqual(FAILURE_MODE_PRIMITIVES & SOUND_REASONING_PRIMITIVES, set())

    def test_failure_mode_default_includes_survivorship_and_unfalsifiability(self):
        # Pinning the defaults — Founder-OS approval gates depend on this set.
        self.assertIn("survivorship_bias", FAILURE_MODE_PRIMITIVES)
        self.assertIn("falsifiability", FAILURE_MODE_PRIMITIVES)


class TestClassifyBelief(unittest.TestCase):
    """``classify_belief()`` — stateless one-shot classification."""

    def test_returns_classification_result_pydantic_model(self):
        r = classify_belief("Steve Jobs dropped out and became a billionaire.")
        self.assertIsInstance(r, ClassificationResult)
        self.assertEqual(r.mechanism, "survivorship_bias")
        self.assertEqual(r.method, "offline-keyword")
        self.assertIn(r.evidence_strength, ("strong", "moderate", "weak"))
        # No confidence/reasoning on the keyword path — these are LLM-only.
        self.assertIsNone(r.confidence)
        self.assertIsNone(r.reasoning)

    def test_off_topic_returns_unknown_reject(self):
        r = classify_belief("Bananas turn yellow when ripe.")
        self.assertEqual(r.mechanism, "unknown")
        self.assertEqual(r.decision, "REJECT")

    def test_evidence_strength_propagates(self):
        # Citation-rich text should classify as 'strong' evidence.
        r = classify_belief(
            "Tetlock (2015) https://doi.org/10.1234/x dropped out and "
            "became a billionaire — survivorship bias. arXiv:1503.04567"
        )
        self.assertEqual(r.evidence_strength, "strong")


class TestCheckDecisionText(unittest.TestCase):
    """``check_decision_text()`` — Founder-OS pattern."""

    def test_failure_mode_primitive_flags_for_review(self):
        r = check_decision_text(
            "Drop out — Jobs and Gates dropped out and became billionaires."
        )
        self.assertIsInstance(r, DecisionCheckResult)
        self.assertTrue(r.flag_for_review)
        self.assertEqual(r.classification.mechanism, "survivorship_bias")
        self.assertIsNotNone(r.flag_reason)
        self.assertIn("survivorship_bias", r.flag_reason)

    def test_sound_reasoning_does_not_flag(self):
        r = check_decision_text(
            "We should compute the expected value before taking this 1% chance bet."
        )
        self.assertFalse(r.flag_for_review)
        self.assertEqual(r.classification.mechanism, "expected_value")
        self.assertIsNone(r.flag_reason)

    def test_unknown_does_not_flag_by_default(self):
        # Conservative consumers can opt in via flag_unknown=True;
        # default behaviour is to NOT flag unknown.
        r = check_decision_text("Bananas turn yellow when ripe.")
        self.assertFalse(r.flag_for_review)

    def test_flag_unknown_opt_in_works(self):
        r = check_decision_text(
            "Bananas turn yellow when ripe.", flag_unknown=True
        )
        self.assertTrue(r.flag_for_review)
        self.assertIn("did not match", r.flag_reason)

    def test_failure_mode_override(self):
        # Override the failure-mode set — make ``expected_value`` a flag.
        # (Useful for risk-averse products that want to flag ANY EV
        # reasoning to a human.)
        r = check_decision_text(
            "Take the bet — expected value is positive.",
            failure_mode_primitives={"expected_value"},
        )
        self.assertTrue(r.flag_for_review)
        self.assertEqual(r.classification.mechanism, "expected_value")


class TestBeliefOSClass(unittest.TestCase):
    """Class-level state: per-consumer ontology + use_llm + failure-mode set."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="belief_os_test_"))
        version_registry.set_registry_path(self.tmp_dir / "registry.jsonl")
        primitive_feedback.FEEDBACK_PATH = self.tmp_dir / "feedback.jsonl"
        primitive_feedback.reset_for_tests()

    def test_classify_no_persistence(self):
        # No ontology_path → in-memory only. Classify still works.
        b = BeliefOS()
        r = b.classify("I should outsell them by dropping our price.")
        self.assertEqual(r.mechanism, "second_order_thinking")

    def test_check_decision_uses_instance_failure_mode_set(self):
        b = BeliefOS(failure_mode_primitives={"second_order_thinking"})
        r = b.check_decision(
            "Don't drop our price — second-order effects kill the win."
        )
        # Now this *is* flagged because we overrode the failure set.
        self.assertTrue(r.flag_for_review)

    def test_query_returns_pydantic_records(self):
        b = BeliefOS()
        records = b.query()
        self.assertEqual(len(records), 6)  # 6 primitives
        for rec in records:
            self.assertIsInstance(rec, BeliefRecord)
            self.assertTrue(rec.definition)
            self.assertTrue(rec.aliases)

    def test_query_filtered_by_primitive(self):
        b = BeliefOS()
        records = b.query(primitive="bayesian_updating")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].primitive, "bayesian_updating")

    def test_query_unknown_primitive_returns_empty(self):
        b = BeliefOS()
        records = b.query(primitive="not_a_real_primitive")
        self.assertEqual(records, [])


class TestIngestPersistence(unittest.TestCase):
    """``BeliefOS.ingest()`` — the L1 closed loop with per-consumer persistence."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="belief_ingest_test_"))
        version_registry.set_registry_path(self.tmp_dir / "registry.jsonl")
        primitive_feedback.FEEDBACK_PATH = self.tmp_dir / "feedback.jsonl"
        primitive_feedback.reset_for_tests()
        self.user_graph = self.tmp_dir / "user_priors.json"

    def test_ingest_with_persistence_writes_ontology_file(self):
        b = BeliefOS(ontology_path=self.user_graph)
        contradiction = (
            "Tetlock (2015) https://doi.org/10.1234/superforecasting "
            "show that the brain does not update beliefs by Bayesian "
            "multiplication when priors are stale. arXiv:1503.04567"
        )
        result = b.ingest(contradiction, source_type="research_paper")
        self.assertIsInstance(result, IngestResult)
        self.assertEqual(result.classification.mechanism, "bayesian_updating")
        self.assertTrue(result.contradicts_prior)
        self.assertEqual(result.merge_status, "merged")
        self.assertEqual(result.primitive_updated, "bayesian_updating")
        self.assertTrue(self.user_graph.exists())

        # Subsequent query reads from the persisted file and surfaces
        # the new sources.
        recs = b.query(primitive="bayesian_updating")
        self.assertEqual(len(recs), 1)
        self.assertGreaterEqual(len(recs[0].sources), 1)

    def test_ingest_in_memory_returns_no_path_in_result(self):
        b = BeliefOS()  # no ontology_path
        result = b.ingest("Steve Jobs dropped out and became a billionaire.")
        self.assertIsNone(result.ontology_path)

    def test_ingest_no_contradiction_yields_no_proposal(self):
        b = BeliefOS(ontology_path=self.user_graph)
        # Aligned with existing definition → no contradiction → no merge.
        aligned = (
            "Beliefs are probabilistic; the brain updates them by "
            "multiplying the prior by the likelihood of new evidence."
        )
        result = b.ingest(aligned)
        self.assertFalse(result.contradicts_prior)
        self.assertEqual(result.merge_status, "no_proposal")


class TestNoLeakageBetweenInstances(unittest.TestCase):
    """Two BeliefOS instances with different settings must not interfere."""

    def test_two_instances_with_different_failure_modes(self):
        b1 = BeliefOS(failure_mode_primitives={"survivorship_bias"})
        b2 = BeliefOS(failure_mode_primitives={"expected_value"})

        text = "Take the bet — expected value is positive."

        r1 = b1.check_decision(text)
        r2 = b2.check_decision(text)

        # Same input, different flag because of different failure sets.
        self.assertFalse(r1.flag_for_review)
        self.assertTrue(r2.flag_for_review)


if __name__ == "__main__":
    unittest.main()
