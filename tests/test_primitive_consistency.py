import unittest

from agent.primitive_consistency_checker import (
    PrimitiveClaim,
    check_primitive_consistency,
    detect_pair_contradiction,
)


class TestPrimitiveConsistency(unittest.TestCase):

    def test_direct_contradiction_high(self):
        a = PrimitiveClaim("attention", "Attention gates which signals control processing")
        b = PrimitiveClaim("attention_alt", "Attention does not gate which signals control processing")

        result = check_primitive_consistency([a, b])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertGreaterEqual(result["finding_count"], 1)
        self.assertEqual(result["findings"][0]["severity"], "high")

    def test_no_overlap_no_flag(self):
        a = PrimitiveClaim("attention", "Attention gates signals")
        b = PrimitiveClaim("rl", "Reward updates value estimates")

        result = check_primitive_consistency([a, b])
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["finding_count"], 0)

    def test_absolute_language_scope_review(self):
        a = PrimitiveClaim("rl", "Learning always depends on reward signals")
        b = PrimitiveClaim("unsup", "Learning never depends on reward signals")

        finding = detect_pair_contradiction(a, b)
        self.assertIsNotNone(finding)
        self.assertIn(finding.severity, ["medium", "high"])

    def test_symmetry_detection(self):
        a = PrimitiveClaim("x", "Model increases prediction error weighting")
        b = PrimitiveClaim("y", "Model decreases prediction error weighting")

        result = check_primitive_consistency([a, b])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()
