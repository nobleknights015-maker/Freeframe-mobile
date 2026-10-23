import unittest

from production_request_builder import (
    PRODUCTION_REQUEST_BUILDER_VERSION,
    build_production_request,
)


class ProductionRequestBuilderTests(unittest.TestCase):
    def test_character_gets_validated_trinity_style(self):
        request = build_production_request("plushbound_character", "adult traveler", seed=1)
        self.assertEqual(request["production_request_builder_version"], PRODUCTION_REQUEST_BUILDER_VERSION)
        self.assertEqual(PRODUCTION_REQUEST_BUILDER_VERSION, "production-request-v2")
        self.assertEqual(request["production_style_profile"], "plushbound_trinity")
        self.assertTrue(request["production_style_validated"])
        self.assertNotIn("guardian_composition_repair", request)
        self.assertIsNone(request["production_reference_validated_mode"])

    def test_guardian_gets_composition_repair_without_unvalidated_style(self):
        request = build_production_request("plushbound_guardian", "small mossbun Plush Guardian", seed=2)
        self.assertTrue(request["guardian_composition_repair"])
        self.assertEqual(request["guardian_composition_version"], "guardian-single-view-v3")
        self.assertIsNone(request["production_style_profile"])
        self.assertFalse(request["production_style_validated"])

    def test_enemy_and_environment_get_category_specific_validated_styles(self):
        cases = {
            "plushbound_enemy": "plushbound_trinity_creature",
            "plushbound_environment": "plushbound_trinity_environment",
        }
        for preset, expected_profile in cases.items():
            with self.subTest(preset=preset):
                request = build_production_request(preset, "test subject", seed=3)
                self.assertEqual(request["production_style_profile"], expected_profile)
                self.assertTrue(request["production_style_validated"])

    def test_approved_reference_is_always_style_only(self):
        reference_id = "a" * 64
        request = build_production_request(
            "plushbound_guardian",
            "small emberfox Plush Guardian",
            seed=4,
            reference_id=reference_id,
            reference_scale=0.42,
        )
        self.assertEqual(request["reference_id"], reference_id)
        self.assertEqual(request["reference_scale"], 0.42)
        self.assertEqual(request["reference_mode"], "style")
        self.assertEqual(request["production_reference_validated_mode"], "style")

    def test_invalid_reference_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            build_production_request(
                "plushbound_guardian", "guardian", seed=5, reference_id="not-a-sha"
            )
        with self.assertRaises(ValueError):
            build_production_request(
                "plushbound_guardian", "guardian", seed=5, reference_id="b" * 64, reference_scale=1.5
            )


if __name__ == "__main__":
    unittest.main()
