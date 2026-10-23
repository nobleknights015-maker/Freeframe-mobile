import unittest
from production_request_builder import PRODUCTION_REQUEST_BUILDER_VERSION,build_production_request
class ProductionRequestBuilderTests(unittest.TestCase):
 def test_character_gets_validated_style_without_creature_policy(self):
  r=build_production_request("plushbound_character","adult traveler",seed=1); self.assertEqual(PRODUCTION_REQUEST_BUILDER_VERSION,"production-request-v4-family-aware"); self.assertEqual(r["production_style_profile"],"plushbound_trinity"); self.assertFalse(r["creature_world_policy_applied"]); self.assertIsNone(r["creature_family"])
 def test_friendly_guardian_gets_friendly_composition(self):
  r=build_production_request("plushbound_guardian","small leaf-eared Guardian",seed=2); self.assertEqual(r["creature_family"],"guardian_friendly"); self.assertEqual(r["guardian_composition_family"],"guardian_friendly"); self.assertIn("small-to-medium companion creature",r["prompt"]); self.assertIn("matte woven textile skin",r["prompt"])
 def test_corrupt_and_boss_use_distinct_composition(self):
  corrupt=build_production_request("plushbound_guardian","damaged woodland Guardian",seed=3,creature_family="guardian_corrupt"); boss=build_production_request("plushbound_guardian","ancient grove Guardian",seed=4,creature_family="guardian_boss")
  self.assertIn("hostile corrupted Guardian",corrupt["prompt"]); self.assertIn("tangled thread and cotton-like inner fiber",corrupt["prompt"]); self.assertIn("large imposing nonhuman Guardian boss",boss["prompt"]); self.assertIn("never a muscular human-shaped bodybuilder",boss["prompt"]); self.assertIn("gorilla",boss["negative_prompt"])
 def test_enemy_gets_living_textile_contract(self):
  r=build_production_request("plushbound_enemy","forest prowler",seed=5); self.assertEqual(r["creature_family"],"enemy_creature"); self.assertIn("same living textile ecosystem",r["prompt"]); self.assertIn("realistic fur coat",r["negative_prompt"])
 def test_reference_is_style_only(self):
  rid="a"*64; r=build_production_request("plushbound_guardian","emberfox",seed=6,reference_id=rid,reference_scale=.42); self.assertEqual(r["reference_mode"],"style"); self.assertEqual(r["production_reference_validated_mode"],"style")
 def test_invalid_inputs_fail_closed(self):
  with self.assertRaises(ValueError): build_production_request("plushbound_guardian","guardian",seed=7,reference_id="bad")
  with self.assertRaises(ValueError): build_production_request("plushbound_enemy","monster",seed=7,creature_family="guardian_corrupt")
if __name__=="__main__": unittest.main()
