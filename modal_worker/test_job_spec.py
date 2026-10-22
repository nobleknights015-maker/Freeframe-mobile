import unittest

from job_spec import AssetJob


class AssetJobTests(unittest.TestCase):
    def make_job(self, **changes):
        values = dict(
            path="characters/hero_001.png",
            category="character",
            profile="generic_rgba_png",
            prompt="adult fantasy traveler",
            negative_prompt="text, malformed anatomy",
            seed=42,
            width=768,
            height=1024,
            steps=28,
            guidance_scale=6.0,
            model_id="candidate/model",
            style_preset="plushbound_character",
            output_path="output/characters/hero_001.png",
            reference_id=None,
        )
        values.update(changes)
        return AssetJob(**values)

    def test_identity_is_deterministic(self):
        self.assertEqual(self.make_job().asset_id, self.make_job().asset_id)

    def test_every_generation_relevant_field_changes_identity(self):
        baseline = self.make_job().asset_id
        variants = {
            "prompt": "different prompt",
            "negative_prompt": "different negative",
            "seed": 43,
            "width": 776,
            "height": 1032,
            "steps": 29,
            "guidance_scale": 5.5,
            "model_id": "other/model",
            "style_preset": "other_style",
            "reference_id": "ref-1",
        }
        for field, value in variants.items():
            with self.subTest(field=field):
                self.assertNotEqual(baseline, self.make_job(**{field: value}).asset_id)

    def test_manifest_contains_asset_id(self):
        job = self.make_job()
        record = job.manifest_record()
        self.assertEqual(record["asset_id"], job.asset_id)
        self.assertEqual(record["output_path"], job.output_path)


if __name__ == "__main__":
    unittest.main()
