import unittest

from production_presets import get_preset
from production_style_policy import (
    PRODUCTION_STYLE_POLICY_VERSION,
    apply_production_style,
    style_for_preset,
)


class ProductionStylePolicyTests(unittest.TestCase):
    def test_validated_presets_use_category_specific_styles(self):
        cases = (
            ("plushbound_character", "adult traveler", "plushbound_trinity"),
            ("plushbound_guardian", "small foxlike plush guardian", "plushbound_guardian_2d_candidate"),
            ("plushbound_enemy", "quadruped forest beast", "plushbound_trinity_creature"),
            ("plushbound_environment", "sunny plains and winding road", "plushbound_trinity_environment"),
        )
        for preset_name, prompt, expected_profile in cases:
            with self.subTest(preset=preset_name):
                base = get_preset(preset_name).apply(prompt, seed=7)
                styled = apply_production_style(preset_name, base)
                self.assertEqual(style_for_preset(preset_name), expected_profile)
                self.assertTrue(styled["production_style_validated"])
                self.assertEqual(styled["production_style_profile"], expected_profile)
                self.assertEqual(styled["render_style_profile"], expected_profile)
                self.assertEqual(styled["production_style_policy_version"], PRODUCTION_STYLE_POLICY_VERSION)
                self.assertIn("sharp", styled["prompt"])

    def test_character_preserves_full_length_composition_language(self):
        base = get_preset("plushbound_character").apply("adult traveler", seed=7)
        styled = apply_production_style("plushbound_character", base)
        self.assertIn("single candid full-length scene", styled["prompt"])
        self.assertIn("current-generation console-RPG promotional art", styled["prompt"])

    def test_guardian_uses_validated_companion_style(self):
        base = get_preset("plushbound_guardian").apply("small foxlike plush guardian", seed=9)
        styled = apply_production_style("plushbound_guardian", base)
        self.assertTrue(styled["production_style_validated"])
        self.assertEqual(styled["production_style_profile"], "plushbound_guardian_2d_candidate")
        self.assertEqual(styled["render_style_profile"], "plushbound_guardian_2d_candidate")
        self.assertIn("companion-creature key art", styled["prompt"])

    def test_unknown_preset_fails_closed_to_no_style(self):
        request = {"prompt": "test", "negative_prompt": ""}
        styled = apply_production_style("unknown", request)
        self.assertFalse(styled["production_style_validated"])
        self.assertIsNone(styled["production_style_profile"])


if __name__ == "__main__":
    unittest.main()
