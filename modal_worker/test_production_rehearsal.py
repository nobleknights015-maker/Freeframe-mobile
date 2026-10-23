import unittest

from production_rehearsal import plan_rehearsal, rehearsal_passes


class ProductionRehearsalTests(unittest.TestCase):
    def _items(self):
        profiles = ["character", "guardian", "enemy", "environment", "portrait", "sprite", "tileset", "icon"]
        return [{"asset_id": f"{p}-{i}", "profile": p, "seed": 1000+i} for p in profiles for i in range(20)]

    def test_default_rehearsal_is_bounded_and_category_balanced(self):
        plan = plan_rehearsal(self._items())
        self.assertEqual(plan["count"], 32)
        self.assertEqual(len(plan["profiles"]), 8)
        self.assertEqual(len(set(plan["asset_ids"])), 32)
        self.assertTrue(plan["requires_explicit_full_batch_approval"])

    def test_plan_is_deterministic(self):
        self.assertEqual(plan_rehearsal(self._items())["asset_ids"], plan_rehearsal(self._items())["asset_ids"])

    def test_limit_is_hard_bounded(self):
        with self.assertRaises(ValueError): plan_rehearsal(self._items(), limit=0)
        with self.assertRaises(ValueError): plan_rehearsal(self._items(), limit=129)

    def test_missing_identity_rejected(self):
        with self.assertRaises(ValueError): plan_rehearsal([{"profile": "character"}])

    def test_gate_requires_high_completion_and_low_unresolved(self):
        self.assertTrue(rehearsal_passes({"total": 32, "completion_rate": 1.0, "unresolved": 0}))
        self.assertFalse(rehearsal_passes({"total": 32, "completion_rate": 0.90, "unresolved": 0}))
        self.assertFalse(rehearsal_passes({"total": 32, "completion_rate": 1.0, "unresolved": 2}))


if __name__ == "__main__":
    unittest.main()
