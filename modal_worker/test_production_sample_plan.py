import unittest

from production_sample_plan import SAMPLES, SAMPLE_PLAN_VERSION, sample_manifest


class ProductionSamplePlanTests(unittest.TestCase):
    def test_sample_plan_is_small_and_complete(self):
        self.assertEqual(len(SAMPLES), 4)
        self.assertEqual({s.sample_id for s in SAMPLES}, {
            "character_master", "guardian_master", "enemy_master", "elyndor_environment"
        })

    def test_samples_use_unique_deterministic_seeds(self):
        seeds = [sample.seed for sample in SAMPLES]
        self.assertEqual(len(seeds), len(set(seeds)))
        self.assertTrue(all(seed > 0 for seed in seeds))

    def test_manifest_locks_v3_identity(self):
        manifest = sample_manifest()
        self.assertEqual(manifest["sample_plan_version"], SAMPLE_PLAN_VERSION)
        self.assertEqual(manifest["style_version"], "v3")
        self.assertEqual(manifest["count"], 4)
        self.assertTrue(all(item["style_version"] == "v3" for item in manifest["samples"]))

    def test_every_sample_has_a_production_purpose(self):
        for sample in SAMPLES:
            with self.subTest(sample=sample.sample_id):
                self.assertTrue(sample.prompt.strip())
                self.assertTrue(sample.purpose.strip())
                self.assertTrue(sample.preset.startswith("plushbound_"))


if __name__ == "__main__":
    unittest.main()
