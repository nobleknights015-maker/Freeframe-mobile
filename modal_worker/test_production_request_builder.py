import unittest
from production_request_builder import PRODUCTION_REQUEST_BUILDER_VERSION,build_production_request
class ProductionRequestBuilderTests(unittest.TestCase):
 def test_character_gets_validated_trinity_style_without_creature_policy(self):
  r=build_production_request("plushbound_character","adult traveler",seed=1); self.assertEqual(PRODUCTION_REQUEST_BUILDER_VERSION,"production-request-v3-living-fabric"); self.assertEqual(r["production_style_profile"],"plushbound_trinity"); self.assertFalse(r["creature_world_policy_applied"]); self.assertIsNone(r["creature_family"])
 def test_guardian_gets_composition_style_and_living_fabric_contract(self):
  r=build_production_request("plushbound_guardian","small mossbun Plush Guardian",seed=2); self.assertTrue(r["guardian_composition_repair"]); self.assertEqual(r["guardian_composition_version"],"guardian-single-view-v4"); self.assertEqual(r["creature_family"],"guardian_friendly"); self.assertIn("living organism native to Plushtopia",r["prompt"]); self.assertIn("retail plush toy",r["negative_prompt"])
 def test_explicit_corrupt_and_boss_guardian_families(self):
  for family,needle in (("guardian_corrupt","torn seams"),("guardian_boss","ancient elite boss-tier")):
   r=build_production_request("plushbound_guardian","woodland Guardian",seed=3,creature_family=family); self.assertEqual(r["creature_family"],family); self.assertIn(needle,r["prompt"])
 def test_enemy_gets_living_textile_contract(self):
  r=build_production_request("plushbound_enemy","forest prowler",seed=4); self.assertEqual(r["creature_family"],"enemy_creature"); self.assertIn("wild hostile Plushtopia creature",r["prompt"]); self.assertIn("ordinary flesh-and-fur animal",r["negative_prompt"])
 def test_reference_is_style_only(self):
  rid="a"*64; r=build_production_request("plushbound_guardian","emberfox",seed=6,reference_id=rid,reference_scale=.42); self.assertEqual(r["reference_mode"],"style"); self.assertEqual(r["production_reference_validated_mode"],"style")
 def test_invalid_inputs_fail_closed(self):
  with self.assertRaises(ValueError): build_production_request("plushbound_guardian","guardian",seed=7,reference_id="bad")
  with self.assertRaises(ValueError): build_production_request("plushbound_enemy","monster",seed=7,creature_family="guardian_corrupt")
if __name__=="__main__": unittest.main()
