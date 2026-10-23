import unittest

from production_presets import get_preset
from production_style_policy import (
    PRODUCTION_STYLE_POLICY_VERSION,
    apply_production_style,
    style_for_preset,
)


class ProductionStylePolicyTests(unittest.TestCase):
    def test_character_uses_validated_trinity_style(self):
        base = get_preset("plushbound_character").apply("adult traveler", seed=7)
        styled = apply_production_style("plushbound_character", base)
        self.assertEqual(style_for_preset("plushbound_character"), "plushbound_trinity")
        self.assertTrue(styled["production_style_validated"])
        self.assertEqual(styled["production_style_profile"], "plushbound_trinity")
        self.assertEqual(styled["render_style_profile"], "plushbound_trinity")
        self.assertEqual(styled["production_style_policy_version"], PRODUCTION_STYLE_POLICY_VERSION)
        self.assertIn("bright modern fantasy JRPG key art", styled["prompt"])
        self.assertIn("single candid full-length scene", styled["prompt"])

    def test_unvalidated_presets_remain_unchanged_in_prompt(self):
        for preset_name in ("plushbound_guardian", "plushbound_enemy", "plushbound_environment"):
            with self.subTest(preset=preset_name):
                base = get_preset(preset_name).apply("test subject", seed=9)
                styled = apply_production_style(preset_name, base)
                self.assertEqual(styled["prompt"], base["prompt"])
                self.assertEqual(styled["negative_prompt"], base["negative_prompt"])
                self.assertFalse(styled["production_style_validated"])
                self.assertIsNone(styled["production_style_profile"])
                self.assertNotIn("render_style_profile", styled)

    def test_unknown_preset_fails_closed_to_no_style(self):
        request = {"prompt": "test", "negative_prompt": ""}
        styled = apply_production_style("unknown", request)
        self.assertFalse(styled["production_style_validated"])
        self.assertIsNone(styled["production_style_profile"])


if __name__ == "__main__":
    unittest.main()
