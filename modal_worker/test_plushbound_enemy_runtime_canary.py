import unittest

from plushbound_enemy_runtime_canary import deterministic_replay


class PlushboundEnemyRuntimeCanaryTests(unittest.TestCase):
    def test_enemy_runtime_canary_replays_identically(self):
        result = deterministic_replay()
        self.assertTrue(result["ok"], result.get("errors"))
        self.assertEqual(result["asset_count"], 8)


if __name__ == "__main__":
    unittest.main()
