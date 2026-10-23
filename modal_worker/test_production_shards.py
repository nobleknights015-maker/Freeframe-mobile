import unittest

from production_shards import shard_index, shard_manifest, split_into_shards


class ProductionShardTests(unittest.TestCase):
    def test_assignment_is_deterministic(self):
        self.assertEqual(shard_index("asset-123", 16), shard_index("asset-123", 16))

    def test_split_preserves_every_asset_exactly_once(self):
        items = [{"asset_id": f"asset-{i}"} for i in range(22000)]
        shards = split_into_shards(items, 16)
        flattened = [x["asset_id"] for shard in shards for x in shard]
        self.assertEqual(len(flattened), 22000)
        self.assertEqual(len(set(flattened)), 22000)
        self.assertEqual(set(flattened), {x["asset_id"] for x in items})

    def test_22k_distribution_has_no_pathological_hot_shard(self):
        items = [{"asset_id": f"asset-{i}"} for i in range(22000)]
        counts = [len(s) for s in split_into_shards(items, 16)]
        average = 22000 / 16
        self.assertLess(max(counts), average * 1.15)
        self.assertGreater(min(counts), average * 0.85)

    def test_manifest_is_complete(self):
        items = [{"asset_id": f"asset-{i}"} for i in range(100)]
        m = shard_manifest(items, 8)
        self.assertEqual(m["total"], 100)
        self.assertEqual(m["shard_count"], 8)
        self.assertEqual(sum(s["count"] for s in m["shards"]), 100)

    def test_missing_identity_and_invalid_count_rejected(self):
        with self.assertRaises(ValueError): split_into_shards([{}], 2)
        with self.assertRaises(ValueError): split_into_shards([], 0)


if __name__ == "__main__":
    unittest.main()
