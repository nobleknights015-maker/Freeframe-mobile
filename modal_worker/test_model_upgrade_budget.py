import unittest

from model_upgrade_budget import benchmark_decision, project_budget


class ModelUpgradeBudgetTests(unittest.TestCase):
    def test_three_seconds_stays_inside_target(self):
        projection = project_budget(3.0)
        self.assertEqual(projection.projected_raw_gpu_usd, 14.65)
        self.assertTrue(projection.within_target)
        self.assertTrue(projection.within_hard_ceiling)

    def test_five_seconds_stays_inside_target(self):
        projection = project_budget(5.0)
        self.assertEqual(projection.projected_raw_gpu_usd, 24.42)
        self.assertTrue(projection.within_target)

    def test_six_seconds_exceeds_target_but_not_hard_ceiling(self):
        decision = benchmark_decision(6.0)
        self.assertEqual(decision["projected_raw_gpu_usd"], 29.3)
        self.assertEqual(decision["status"], "target")
        self.assertFalse(decision["production_authorized"])

    def test_eight_seconds_is_caution(self):
        decision = benchmark_decision(8.0)
        self.assertEqual(decision["projected_raw_gpu_usd"], 39.07)
        self.assertEqual(decision["status"], "caution")
        self.assertFalse(decision["production_authorized"])

    def test_nine_seconds_rejected(self):
        decision = benchmark_decision(9.0)
        self.assertEqual(decision["projected_raw_gpu_usd"], 43.96)
        self.assertEqual(decision["status"], "reject")
        self.assertFalse(decision["production_authorized"])

    def test_invalid_values_fail_closed(self):
        with self.assertRaises(ValueError):
            project_budget(-0.1)
        with self.assertRaises(ValueError):
            project_budget(1.0, projected_assets=0)
        with self.assertRaises(ValueError):
            project_budget(1.0, target_monthly_compute_usd=40.0, hard_monthly_compute_ceiling_usd=30.0)


if __name__ == "__main__":
    unittest.main()
