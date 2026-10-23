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
                self.assertEqual(applied["render_style_version"], "mt1.2")
                self.assertEqual(applied["seed"], 42)
                self.assertTrue(applied["prompt"].startswith("adult fantasy traveler. "))
                self.assertLess(applied["prompt"].index(profile.positive), applied["prompt"].index("A single candid full-length scene"))
                self.assertTrue(applied["negative_prompt"].startswith(profile.negative))
                self.assertIn("retro visual-novel softness", applied["negative_prompt"])
                self.assertEqual(profile.metadata()["version"], STYLE_PROFILE_VERSION)

    def test_hybrid_keeps_compact_modern_jrpg_target(self):
        text = get_style_profile("plushbound_hybrid").positive
        self.assertIn("modern fantasy JRPG key art", text)
        self.assertIn("crisp anime face and linework", text)
        self.assertIn("vivid controlled colors", text)
        self.assertIn("restrained bloom", text)
        self.assertLessEqual(len(text.split()), 32)

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
