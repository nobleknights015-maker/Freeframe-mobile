import unittest

from production_request_builder import (
    PRODUCTION_REQUEST_BUILDER_VERSION,
    build_production_request,
)


class ProductionRequestBuilderTests(unittest.TestCase):
    def test_character_gets_validated_trinity_style(self):
        request = build_production_request("plushbound_character", "adult traveler", seed=1)
        self.assertEqual(request["production_request_builder_version"], PRODUCTION_REQUEST_BUILDER_VERSION)
        self.assertEqual(request["production_style_profile"], "plushbound_trinity")
        self.assertTrue(request["production_style_validated"])
        self.assertNotIn("guardian_composition_repair", request)

    def test_guardian_gets_composition_repair_without_unvalidated_style(self):
        request = build_production_request("plushbound_guardian", "small mossbun Plush Guardian", seed=2)
        self.assertTrue(request["guardian_composition_repair"])
        self.assertEqual(request["guardian_composition_version"], "guardian-single-view-v2")
        self.assertIsNone(request["production_style_profile"])
        self.assertFalse(request["production_style_validated"])

    def test_enemy_and_environment_get_validated_trinity_style(self):
        for preset in ("plushbound_enemy", "plushbound_environment"):
            with self.subTest(preset=preset):
                request = build_production_request(preset, "test subject", seed=3)
                self.assertEqual(request["production_style_profile"], "plushbound_trinity")
                self.assertTrue(request["production_style_validated"])


if __name__ == "__main__":
    unittest.main()
