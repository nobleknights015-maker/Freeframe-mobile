import unittest

from model_catalog import PRODUCTION_RENDERER_KEY, get_production_renderer
from production_model_policy import (
    PRODUCTION_MODEL_POLICY_VERSION,
    PRODUCTION_RENDERER_ROUTE,
    apply_production_model_policy,
)
from production_request_builder import build_production_request


class ProductionModelPolicyTests(unittest.TestCase):
    def test_promoted_renderer_is_klein_and_bounded_only(self):
        candidate = get_production_renderer()
        self.assertEqual(candidate.key, PRODUCTION_RENDERER_KEY)
        self.assertEqual(candidate.model_id, "black-forest-labs/FLUX.2-klein-4B")
        self.assertTrue(candidate.production_eligible)

        request = build_production_request(
            "plushbound_character",
            "one adult Elyndor courier, full body",
            seed=123,
        )
        self.assertEqual(request["renderer_route"], PRODUCTION_RENDERER_ROUTE)
        self.assertEqual(request["renderer_class"], "FreeFrameProductionGenerator")
        self.assertEqual(request["model_id"], candidate.model_id)
        self.assertEqual(request["model_candidate"], candidate.key)
        self.assertEqual(request["steps"], 4)
        self.assertEqual(request["guidance_scale"], 1.0)
        self.assertEqual(request["production_model_policy_version"], PRODUCTION_MODEL_POLICY_VERSION)
        self.assertTrue(request["bounded_production_authorized"])
        self.assertFalse(request["automatic_full_production_authorized"])
        self.assertFalse(request["catalog_wide_launch_authorized"])

    def test_all_supported_master_presets_route_to_klein(self):
        for preset, family in (
            ("plushbound_character", None),
            ("plushbound_guardian", "guardian_friendly"),
            ("plushbound_enemy", "enemy_creature"),
            ("plushbound_environment", None),
        ):
            with self.subTest(preset=preset):
                request = build_production_request(
                    preset,
                    "single bounded production representative",
                    seed=44,
                    creature_family=family,
                )
                self.assertEqual(request["renderer_route"], PRODUCTION_RENDERER_ROUTE)
                self.assertEqual(request["model_id"], "black-forest-labs/FLUX.2-klein-4B")
                self.assertEqual(request["steps"], 4)
                self.assertEqual(request["guidance_scale"], 1.0)

    def test_policy_fails_closed_for_unsupported_preset(self):
        with self.assertRaisesRegex(ValueError, "not routed"):
            apply_production_model_policy("unknown", {"width": 512, "height": 512})

    def test_policy_rejects_resolution_above_promoted_limit(self):
        with self.assertRaisesRegex(ValueError, "resolution limit"):
            apply_production_model_policy("plushbound_character", {"width": 1536, "height": 1024})


if __name__ == "__main__":
    unittest.main()
