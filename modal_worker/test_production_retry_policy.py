import unittest

from production_retry_policy import RetryPolicy


class RetryPolicyTests(unittest.TestCase):
    def test_deterministic_variants(self):
        p = RetryPolicy(max_attempts=3)
        item = {"path": "Actors/a.png", "profile": "character", "seed": 8201}
        self.assertEqual(p.variant(item, 1)["seed"], 8201)
        self.assertEqual(p.variant(item, 2)["seed"], 112930)
        self.assertEqual(p.variant(item, 3)["seed"], 217659)
        self.assertNotIn("retry_attempt", item)

    def test_attempt_budget_is_bounded(self):
        p = RetryPolicy(max_attempts=3)
        with self.assertRaises(ValueError): p.variant({"seed": 1}, 4)
        with self.assertRaises(ValueError): RetryPolicy(max_attempts=99).validate()

    def test_quarantine_record_preserves_identity_context(self):
        p = RetryPolicy(max_attempts=3)
        record = p.exhausted_record({"path": "Enemies/wolf.png", "profile": "enemy", "seed": 42}, "semantic reject")
        self.assertTrue(record["quarantined"])
        self.assertEqual(record["attempts"], 3)
        self.assertEqual(record["path"], "Enemies/wolf.png")
        self.assertEqual(record["profile"], "enemy")
        self.assertEqual(record["seed"], 42)


if __name__ == "__main__":
    unittest.main()
