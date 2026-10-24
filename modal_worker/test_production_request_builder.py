import unittest
from production_request_builder import PRODUCTION_REQUEST_BUILDER_VERSION, build_production_request


class ProductionRequestBuilderTests(unittest.TestCase):
    def test_character_gets_validated_style_without_creature_policy(self):
        request = build_production_request("plushbound_character", "adult traveler", seed=1)
        self.assertEqual(PRODUCTION_REQUEST_BUILDER_VERSION, "production-request-v5-klein-routed")
        self.assertEqual(request["production_style_profile"], "plushbound_trinity")
        self.assertFalse(request["creature_world_policy_applied"])
        self.assertIsNone(request["creature_family"])
        self.assertEqual(request["renderer_route"], "flux2_klein")
        self.assertEqual(request["model_id"], "black-forest-labs/FLUX.2-klein-4B")
        self.assertEqual(request["steps"], 4)
        self.assertEqual(request["guidance_scale"], 1.0)
        self.assertFalse(request["catalog_wide_launch_authorized"])

    def test_friendly_guardian_gets_friendly_enclosed_composition(self):
        request = build_production_request("plushbound_guardian", "small leaf-eared Guardian", seed=2)
        self.assertEqual(request["creature_family"], "guardian_friendly")
        self.assertEqual(request["guardian_composition_family"], "guardian_friendly")
        self.assertIn("small-to-medium companion creature", request["prompt"])
        self.assertIn("creature first and textile biology second", request["prompt"])
        self.assertIn("fully enclosed exterior body", request["prompt"])
        self.assertIn("intact continuous textile integument completely encloses", request["prompt"])
        self.assertIn("visible skeleton", request["negative_prompt"])
        self.assertIn("random patches", request["negative_prompt"])
        self.assertEqual(request["renderer_route"], "flux2_klein")

    def test_corrupt_and_boss_use_distinct_composition(self):
        corrupt = build_production_request("plushbound_guardian", "damaged woodland Guardian", seed=3, creature_family="guardian_corrupt")
        boss = build_production_request("plushbound_guardian", "ancient grove Guardian", seed=4, creature_family="guardian_boss")
        self.assertIn("hostile corrupted Guardian", corrupt["prompt"])
        self.assertIn("cotton-like inner fiber", corrupt["prompt"])
        self.assertIn("never bones ribs spine skull", corrupt["prompt"])
        self.assertIn("large imposing nonhuman Guardian boss", boss["prompt"])
        self.assertIn("massive but functionally built nonhuman body", boss["prompt"])
        self.assertIn("fully enclosed continuous exterior body", boss["prompt"])
        self.assertIn("gorilla", boss["negative_prompt"])
        self.assertIn("skeletal boss", boss["negative_prompt"])

    def test_enemy_gets_living_textile_contract(self):
        request = build_production_request("plushbound_enemy", "forest prowler", seed=5)
        self.assertEqual(request["creature_family"], "enemy_creature")
        self.assertIn("wild hostile Plushtopia species", request["prompt"])
        self.assertIn("completely encloses the whole healthy body", request["prompt"])
        self.assertIn("no bones ribs spine skull", request["prompt"])
        self.assertIn("realistic fur coat", request["negative_prompt"])
        self.assertIn("smiling mascot face", request["negative_prompt"])
        self.assertEqual(request["renderer_route"], "flux2_klein")

    def test_reference_is_style_only(self):
        reference_id = "a" * 64
        request = build_production_request("plushbound_guardian", "emberfox", seed=6, reference_id=reference_id, reference_scale=0.42)
        self.assertEqual(request["reference_mode"], "style")
        self.assertEqual(request["production_reference_validated_mode"], "style")
        self.assertEqual(request["renderer_route"], "flux2_klein")

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            build_production_request("plushbound_guardian", "guardian", seed=7, reference_id="bad")
        with self.assertRaises(ValueError):
            build_production_request("plushbound_enemy", "monster", seed=7, creature_family="guardian_corrupt")


if __name__ == "__main__": unittest.main()
