import unittest

from style_profiles import STYLE_PROFILE_VERSION, STYLE_PROFILES, get_style_profile


class StyleProfileTests(unittest.TestCase):
    def test_profiles_apply_without_mutating_input(self):
        base = {
            "prompt": "adult fantasy traveler",
            "negative_prompt": "text, watermark",
            "width": 768,
            "height": 1024,
            "seed": 42,
        }
        for name, profile in STYLE_PROFILES.items():
            with self.subTest(name=name):
                applied = profile.apply(base)
                self.assertEqual(base["prompt"], "adult fantasy traveler")
                self.assertEqual(applied["render_style_profile"], name)
                self.assertEqual(applied["render_style_version"], "mt1.1")
                self.assertEqual(applied["seed"], 42)
                self.assertTrue(applied["prompt"].startswith(profile.positive))
                self.assertIn("adult fantasy traveler", applied["prompt"])
                self.assertTrue(applied["negative_prompt"].startswith(profile.negative))
                self.assertIn("early-2000s visual novel look", applied["negative_prompt"])
                self.assertEqual(profile.metadata()["version"], STYLE_PROFILE_VERSION)

    def test_hybrid_encodes_mv_readability_and_trinity_polish(self):
        text = get_style_profile("plushbound_hybrid").positive
        self.assertIn("MV-like character readability", text)
        self.assertIn("Trinity-like color and material polish", text)
        self.assertIn("restrained bloom", text)

    def test_profiles_are_visually_distinct(self):
        positives = {profile.positive for profile in STYLE_PROFILES.values()}
        self.assertEqual(len(positives), 3)

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            get_style_profile("plushbound_mv").apply({"prompt": "   "})

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError):
            get_style_profile("missing")


if __name__ == "__main__":
    unittest.main()
