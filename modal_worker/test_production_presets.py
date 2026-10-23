import unittest

from production_presets import PLUSHBOUND_STYLE_VERSION, PRESETS, get_preset


class ProductionPresetTests(unittest.TestCase):
    def test_all_presets_build_valid_requests(self):
        for name, preset in PRESETS.items():
            with self.subTest(name=name):
                request = preset.apply("silver-haired traveler with a small satchel", seed=42)
                self.assertEqual(request["style_preset"], name)
                self.assertEqual(request["style_version"], PLUSHBOUND_STYLE_VERSION)
                self.assertEqual(request["seed"], 42)
                self.assertTrue(request["prompt"])
                self.assertIn("malformed anatomy", request["negative_prompt"])
                self.assertEqual(request["width"] % 8, 0)
                self.assertEqual(request["height"] % 8, 0)
                self.assertGreaterEqual(request["steps"], 20)
                self.assertGreater(request["guidance_scale"], 0)
                self.assertEqual(preset.metadata()["style_version"], PLUSHBOUND_STYLE_VERSION)

    def test_v33_identity_is_current(self):
        self.assertEqual(PLUSHBOUND_STYLE_VERSION, "v3.3")

    def test_shared_style_is_contemporary_not_soft_painterly(self):
        request = get_preset("plushbound_character").apply("adult traveler", seed=1)
        self.assertIn("clean contemporary 2D game illustration", request["prompt"])
        self.assertIn("sharp digital finish", request["prompt"])
        self.assertNotIn("painterly anime-inspired game art", request["prompt"])
        self.assertNotIn("soft dimensional light", request["prompt"])

    def test_character_uses_scene_composition_not_sheet_language(self):
        request = get_preset("plushbound_character").apply("adult traveler", seed=1)
        self.assertIn("single candid full-length scene", request["prompt"])
        self.assertIn("one continuous background", request["prompt"])
        self.assertIn("presentation board", request["negative_prompt"])
        self.assertIn("split screen", request["negative_prompt"])

    def test_enemy_uses_horizontal_quadruped_geometry(self):
        request = get_preset("plushbound_enemy").apply("mossback woodland prowler", seed=2)
        self.assertIn("animal spine parallel to the ground", request["prompt"])
        self.assertIn("front paws and rear paws supporting the body", request["prompt"])
        self.assertIn("gorilla", request["negative_prompt"])
        self.assertIn("upright torso", request["negative_prompt"])
        self.assertGreater(request["width"], request["height"])

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
