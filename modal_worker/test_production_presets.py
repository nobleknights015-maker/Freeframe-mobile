import unittest

from production_presets import PLUSHBOUND_STYLE_VERSION, PRESETS, get_preset


class ProductionPresetTests(unittest.TestCase):
    def test_all_presets_build_valid_requests(self):
        for name, preset in PRESETS.items():
            with self.subTest(name=name):
                request = preset.apply("silver-haired traveler with a small satchel", seed=42)
                self.assertEqual(request["style_preset"], name)
                self.assertEqual(request["style_version"], "v3")
                self.assertEqual(request["seed"], 42)
                self.assertTrue(request["prompt"])
                self.assertIn("malformed anatomy", request["negative_prompt"])
                self.assertEqual(request["width"] % 8, 0)
                self.assertEqual(request["height"] % 8, 0)
                self.assertGreaterEqual(request["steps"], 20)
                self.assertGreater(request["guidance_scale"], 0)
                self.assertEqual(preset.metadata()["style_version"], PLUSHBOUND_STYLE_VERSION)

    def test_v3_identity_is_frozen(self):
        self.assertEqual(PLUSHBOUND_STYLE_VERSION, "v3")

    def test_unknown_preset_rejected(self):
        with self.assertRaises(ValueError):
            get_preset("missing")

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            get_preset("plushbound_guardian").apply("   ", seed=1)


if __name__ == "__main__":
    unittest.main()
