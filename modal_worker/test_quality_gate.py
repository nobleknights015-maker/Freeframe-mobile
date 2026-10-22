import unittest

from quality_gate import PromotionPolicy, evaluate


class QualityGateTests(unittest.TestCase):
    def good(self):
        return {
            "cases": 4,
            "integrity_rate": 1.0,
            "visual_score": 8.2,
            "failure_rate": 0.0,
            "projected_gpu_hours_22000": 45.0,
        }

    def test_good_benchmark_is_approved(self):
        decision = evaluate(self.good())
        self.assertTrue(decision.approved)
        self.assertEqual(decision.reasons, ())

    def test_missing_fields_fail_closed(self):
        decision = evaluate({})
        self.assertFalse(decision.approved)
        self.assertGreater(len(decision.reasons), 1)

    def test_visual_quality_blocks_promotion(self):
        summary = self.good()
        summary["visual_score"] = 6.9
        decision = evaluate(summary)
        self.assertFalse(decision.approved)
        self.assertTrue(any("visual" in reason for reason in decision.reasons))

    def test_any_failure_blocks_promotion(self):
        summary = self.good()
        summary["failure_rate"] = 0.25
        decision = evaluate(summary)
        self.assertFalse(decision.approved)

    def test_excessive_projected_time_blocks_promotion(self):
        summary = self.good()
        summary["projected_gpu_hours_22000"] = 121.0
        decision = evaluate(summary, PromotionPolicy(maximum_projected_gpu_hours=120.0))
        self.assertFalse(decision.approved)


if __name__ == "__main__":
    unittest.main()
