"""Tests for the ``personal_epistemic_v1`` domain (Belief OS).

Covers:
1. domain registration round-trip
2. all 6 golden cases classify to the expected reasoning primitive
3. extractor returns the standard ``{knowledge, true_validation, decision}`` shape
4. priority-rules file actually steers extraction (file-based routing works)
5. ingest_documents accepts the new ``golden_cases`` + ``priority_rules_path``
   kwargs and uses them for the golden gate (no merges reverted on a clean
   ingest of an in-domain claim)
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

# Importing the domain module registers personal_epistemic_v1.
import agent.personal_epistemic_domain  # noqa: F401
from agent import primitive_feedback, version_registry
from agent.api import ingest_documents
from agent.domains import get_domain, list_domains
from agent.personal_epistemic_domain import (
    PERSONAL_EPISTEMIC_GOLDEN_CASES,
    PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
    personal_epistemic_extractor,
)


class TestDomainRegistration(unittest.TestCase):
    def test_domain_is_registered(self):
        self.assertIn("personal_epistemic_v1", list_domains())

    def test_domain_metadata(self):
        domain = get_domain("personal_epistemic_v1")
        self.assertEqual(domain.name, "personal_epistemic_v1")
        # Read-only in v1 — the L2 self-modification loop must short-circuit.
        self.assertEqual(domain.mutable_paths, [])
        # Goldens cover all 6 primitives.
        self.assertEqual(len(domain.golden_cases), 6)
        primitive_names = set(domain.ontology["primitives"])
        self.assertEqual(
            primitive_names,
            {
                "bayesian_updating",
                "base_rate_reasoning",
                "falsifiability",
                "expected_value",
                "second_order_thinking",
                "survivorship_bias",
            },
        )


class TestGoldenAccuracy(unittest.TestCase):
    def test_all_goldens_classify_correctly(self):
        domain = get_domain("personal_epistemic_v1")
        misses = []
        for case in domain.golden_cases:
            result = domain.extractor(case["text"])
            actual = result["knowledge"].get("mechanism")
            if actual != case["expected_mechanism"]:
                misses.append(
                    f"expected={case['expected_mechanism']!r} "
                    f"actual={actual!r} text={case['text'][:60]!r}"
                )
        self.assertEqual(misses, [], f"Golden cases misclassified:\n  " + "\n  ".join(misses))

    def test_all_goldens_decide_accept(self):
        # A correctly classified golden with full TRUE coverage should ACCEPT.
        domain = get_domain("personal_epistemic_v1")
        for case in domain.golden_cases:
            result = domain.extractor(case["text"])
            self.assertEqual(
                result["decision"],
                "ACCEPT",
                f"expected ACCEPT for {case['expected_mechanism']!r}",
            )


class TestExtractorShape(unittest.TestCase):
    def test_extractor_returns_pipeline_shape(self):
        result = personal_epistemic_extractor(
            "The reference class is dropouts who tried — base rate matters."
        )
        self.assertIn("knowledge", result)
        self.assertIn("true_validation", result)
        self.assertIn("decision", result)
        self.assertIn("scores", result["true_validation"])
        self.assertEqual(
            result["knowledge"].get("mechanism"),
            "base_rate_reasoning",
        )

    def test_out_of_domain_text_is_unknown(self):
        result = personal_epistemic_extractor(
            "Bananas turn yellow when ripe. They float in fresh water."
        )
        self.assertEqual(result["knowledge"].get("mechanism"), "unknown")
        self.assertEqual(result["decision"], "REJECT")


class TestPriorityRulesFileRouting(unittest.TestCase):
    """The personal-epistemic priority-rules file should actually steer routing.

    A cue that exists *only* in the personal-epistemic file (and not in any
    primitive's aliases) should still route correctly, proving the file is
    plumbed through.
    """

    def test_file_only_cue_routes_to_correct_primitive(self):
        # "kelly criterion" is in the priority-rules file under expected_value
        # and ALSO in the aliases — so this is a smoke test that the file
        # routing path works at all. We can't easily isolate "file-only" cues
        # without polluting the file, so this is a coverage check.
        result = personal_epistemic_extractor(
            "Apply the kelly criterion to size the position."
        )
        self.assertEqual(result["knowledge"].get("mechanism"), "expected_value")

    def test_priority_rules_file_exists(self):
        self.assertTrue(
            PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH.exists(),
            f"missing: {PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH}",
        )


class TestIngestDocumentsWithDomainParams(unittest.TestCase):
    """``ingest_documents`` must accept the new domain kwargs and use them."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="neuro_belief_test_"))
        version_registry.set_registry_path(self.tmp_dir / "version_registry.jsonl")
        primitive_feedback.FEEDBACK_PATH = self.tmp_dir / "primitive_feedback.jsonl"
        primitive_feedback.reset_for_tests()

    def test_in_domain_ingest_does_not_revert_against_belief_goldens(self):
        """A well-cited in-domain claim must not be reverted by goldens
        from the WRONG domain.

        Without ``golden_cases``, ``run_self_evolution`` defaults to the
        neuroscience GOLDEN_CASES — every personal-epistemic merge would
        regress against neuroscience goldens (because the new ontology has
        no neuroscience primitives) and be reverted. Passing the right
        goldens fixes that.
        """
        domain = get_domain("personal_epistemic_v1")
        # Use the survivorship-bias golden as a citation-strong document.
        text = (
            "Wald (1943) https://doi.org/10.1234/wald shows survivorship bias: "
            "the visible sample is the population filtered by selection — "
            "bullet holes only appear on planes that returned. arXiv:1943.0001"
        )

        ontology_copy = {
            "primitives": {
                k: dict(v) for k, v in domain.ontology["primitives"].items()
            }
        }
        report = ingest_documents(
            [text],
            ontology=ontology_copy,
            ontology_path=self.tmp_dir / "ontology.json",
            golden_cases=list(PERSONAL_EPISTEMIC_GOLDEN_CASES),
            priority_rules_path=PERSONAL_EPISTEMIC_PRIORITY_RULES_PATH,
        )

        # No spurious revert from cross-domain goldens.
        self.assertEqual(
            report["merges_reverted"],
            0,
            f"unexpected revert(s): {report.get('registry_entries', [])[-1:]}",
        )

    def test_default_neuroscience_goldens_would_revert_personal_epistemic_merges(self):
        """Sanity check: WITHOUT passing belief goldens, the same ingest
        either does not propose a merge or reverts because neuroscience
        goldens fail. Either outcome confirms the gating works."""
        domain = get_domain("personal_epistemic_v1")
        text = (
            "Wald (1943) https://doi.org/10.1234/wald shows survivorship bias: "
            "the visible sample is the population filtered by selection. "
            "arXiv:1943.0001"
        )
        ontology_copy = {
            "primitives": {
                k: dict(v) for k, v in domain.ontology["primitives"].items()
            }
        }
        report = ingest_documents(
            [text],
            ontology=ontology_copy,
            ontology_path=self.tmp_dir / "ontology2.json",
            # NOTE: omitting golden_cases & priority_rules_path on purpose.
        )
        # Either there were 0 merges_applied (no proposal accepted) or
        # any applied ones were reverted by the wrong-domain goldens.
        self.assertEqual(
            report["merges_applied"],
            0,
            "neuroscience goldens should have gated personal-epistemic merges",
        )


class TestRawClaimCoverage(unittest.TestCase):
    """Lock in that everyday teenager-style phrasings still fire the right
    primitive without requiring the user to type the technical pattern name.

    These are the literal stories from the v1.1 vocabulary expansion. If a
    future edit drops one of the supporting cues, this test will catch it
    before it ships.
    """

    RAW_CLAIMS = [
        (
            "My favorite YouTuber dropped out of college and now makes $50k a "
            "month. Steve Jobs and Bill Gates and Mark Zuckerberg also dropped "
            "out and became billionaires. So dropping out is the smart move "
            "for ambitious people.",
            "survivorship_bias",
        ),
        (
            "My friend tested positive for a rare disease. The test is 99% "
            "accurate. She is panicking. Disease prevalence is 0.1%.",
            "bayesian_updating",
        ),
        (
            "This influencer says wake up at 5am, cold plunge, journal, and "
            "you will be successful. There is no situation where this routine "
            "could be wrong, it works for everyone always.",
            "falsifiability",
        ),
        (
            "The kids next door sold 80 cups today at $2. We should drop our "
            "price to $1 to outsell them tomorrow.",
            "second_order_thinking",
        ),
        (
            "There is a 1% chance this stock 100x and I become rich. The "
            "expected value is the same as keeping the cash, so why not take "
            "the shot?",
            "expected_value",
        ),
    ]

    def test_raw_teenager_claims_classify_correctly(self):
        misses = []
        for claim, expected in self.RAW_CLAIMS:
            result = personal_epistemic_extractor(claim)
            actual = result["knowledge"].get("mechanism")
            if actual != expected:
                misses.append(
                    f"expected={expected!r} actual={actual!r} "
                    f"text={claim[:60]!r}"
                )
        self.assertEqual(misses, [], "raw-claim regressions:\n  " + "\n  ".join(misses))

    def test_out_of_domain_banana_text_still_rejects(self):
        result = personal_epistemic_extractor(
            "Bananas turn yellow when they ripen. They float in fresh water."
        )
        self.assertEqual(result["knowledge"].get("mechanism"), "unknown")
        self.assertEqual(result["decision"], "REJECT")


if __name__ == "__main__":
    unittest.main()
