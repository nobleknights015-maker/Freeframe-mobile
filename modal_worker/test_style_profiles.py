import unittest

from style_profiles import STYLE_PROFILE_VERSION, STYLE_PROFILES, get_style_profile


class StyleProfileTests(unittest.TestCase):
    def test_profiles_apply_without_mutating_input(self):
        base = {
            "prompt": "adult fantasy traveler. A single candid full-length scene containing one adult traveler",
            "negative_prompt": "text, watermark",
            "width": 768,
            "height": 1024,
            "seed": 42,
        }
        for name, profile in STYLE_PROFILES.items():
            with self.subTest(name=name):
                applied = profile.apply(base)
                self.assertEqual(
                    base["prompt"],
                    "adult fantasy traveler. A single candid full-length scene containing one adult traveler",
                )
                self.assertEqual(applied["render_style_profile"], name)
                self.assertEqual(applied["render_style_version"], STYLE_PROFILE_VERSION)
                self.assertEqual(applied["seed"], 42)
                self.assertTrue(applied["prompt"].startswith("adult fantasy traveler. "))
                self.assertLess(
                    applied["prompt"].index(profile.positive),
                    applied["prompt"].index("A single candid full-length scene"),
                )
                self.assertTrue(applied["negative_prompt"].startswith(profile.negative))
                self.assertIn("early-2000s anime-game rendering", applied["negative_prompt"])
                self.assertIn("watercolor haze", applied["negative_prompt"])
                self.assertEqual(profile.metadata()["version"], STYLE_PROFILE_VERSION)

    def test_trinity_character_keeps_contemporary_jrpg_target(self):
        text = get_style_profile("plushbound_trinity").positive
        self.assertIn("contemporary high-budget fantasy JRPG promotional character art", text)
        self.assertIn("crisp modern anime features", text)
        self.assertIn("sophisticated saturated color grading", text)
        self.assertIn("sharp controlled digital finish", text)
        self.assertIn("current-generation console-RPG illustration", text)
        self.assertNotIn("painterly blending", text)

    def test_environment_is_modern_without_poster_cues(self):
        text = get_style_profile("plushbound_trinity_environment").positive
        self.assertIn("contemporary high-budget fantasy JRPG environment illustration", text)
        self.assertIn("sharp modern digital finish", text)
        self.assertIn("no foreground hero", text)
        self.assertIn("no poster composition", text)

    def test_guardian_candidate_is_explicitly_2d_and_non_product(self):
        text = get_style_profile("plushbound_guardian_2d_candidate").positive
        self.assertIn("contemporary 2D fantasy JRPG companion-creature illustration", text)
        self.assertIn("sewn-fabric anatomy", text)
        self.assertIn("sharp digital finish", text)
        self.assertIn("no product-photo lighting", text)
        self.assertIn("no model-sheet layout", text)

    def test_profiles_are_visually_distinct(self):
        positives = {profile.positive for profile in STYLE_PROFILES.values()}
        self.assertEqual(len(positives), len(STYLE_PROFILES))

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            get_style_profile("plushbound_mv").apply({"prompt": "   "})

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError):
            get_style_profile("missing")


if __name__ == "__main__":
    unittest.main()
