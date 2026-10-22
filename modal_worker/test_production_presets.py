import unittest

from production_presets import PLUSHBOUND_STYLE_VERSION, PRESETS, get_preset


class ProductionPresetTests(unittest.TestCase):
    def test_all_presets_build_valid_requests(self):
        for name, preset in PRESETS.items():
            with self.subTest(name=name):
                request = preset.apply("silver-haired traveler with a small satchel", seed=42)
                self.assertEqual(request["style_preset"], name)
                self.assertEqual(request["style_version"], "v3.1")
                self.assertEqual(request["seed"], 42)
                self.assertTrue(request["prompt"])
                self.assertIn("malformed anatomy", request["negative_prompt"])
                self.assertEqual(request["width"] % 8, 0)
                self.assertEqual(request["height"] % 8, 0)
                self.assertGreaterEqual(request["steps"], 20)
                self.assertGreater(request["guidance_scale"], 0)
                self.assertEqual(preset.metadata()["style_version"], PLUSHBOUND_STYLE_VERSION)

    def test_v31_identity_is_frozen(self):
        self.assertEqual(PLUSHBOUND_STYLE_VERSION, "v3.1")

    def test_character_preset_explicitly_blocks_turnarounds(self):
        request = get_preset("plushbound_character").apply("adult traveler", seed=1)
        self.assertIn("exactly one adult human", request["prompt"])
        self.assertIn("exactly one body", request["prompt"])
        self.assertIn("contact sheet", request["negative_prompt"])
        self.assertIn("reference sheet", request["negative_prompt"])

    def test_enemy_preset_requires_non_humanoid_quadruped(self):
        request = get_preset("plushbound_enemy").apply("mossback woodland prowler", seed=2)
        self.assertIn("exactly one hostile quadrupedal creature", request["prompt"])
        self.assertIn("no carried weapon", request["prompt"])
        self.assertIn("humanoid", request["negative_prompt"])
        self.assertIn("axe", request["negative_prompt"])

    def test_guardian_and_environment_keep_existing_semantics(self):
        guardian = get_preset("plushbound_guardian").apply("foxlike guardian", seed=3)
        environment = get_preset("plushbound_environment").apply("sunny plains", seed=4)
        self.assertIn("clearly sewn plush body", guardian["prompt"])
        self.assertIn("Outdoor landscape only", environment["prompt"])

    def test_unknown_preset_rejected(self):
        with self.assertRaises(ValueError):
            get_preset("missing")

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            get_preset("plushbound_guardian").apply("   ", seed=1)


if __name__ == "__main__":
    unittest.main()
