import unittest
from creature_world_policy import CREATURE_WORLD_POLICY_VERSION, apply_creature_world_policy, resolve_creature_family

class CreatureWorldPolicyTests(unittest.TestCase):
 def test_guardian_defaults_to_friendly_living_fabric(self):
  base={"prompt":"small meadow companion. one creature","negative_prompt":"text"}; out=apply_creature_world_policy("plushbound_guardian",base)
  self.assertTrue(out["creature_world_policy_applied"]); self.assertEqual(out["creature_family"],"guardian_friendly"); self.assertEqual(out["creature_world_policy_version"],CREATURE_WORLD_POLICY_VERSION)
  self.assertIn("living fantasy organism native to Plushtopia",out["prompt"]); self.assertIn("creature first and textile biology second",out["prompt"]); self.assertIn("matte woven textile skin",out["prompt"]); self.assertIn("cute through expression and species design rather than stuffed-toy proportions",out["prompt"]); self.assertIn("retail plush toy",out["negative_prompt"]); self.assertIn("realistic fur coat",out["negative_prompt"]); self.assertIn("ordinary flesh-and-fur animal",out["negative_prompt"])
 def test_enemy_forces_living_textile_ecosystem(self):
  out=apply_creature_world_policy("plushbound_enemy",{"prompt":"forest prowler","negative_prompt":""}); self.assertEqual(out["creature_family"],"enemy_creature"); self.assertIn("wild hostile Plushtopia species",out["prompt"]); self.assertIn("same living textile ecosystem",out["prompt"]); self.assertIn("matte woven quilted or layered textile skin",out["prompt"]); self.assertIn("normal wolf",out["negative_prompt"]); self.assertIn("realistic fur coat",out["negative_prompt"])
 def test_corrupt_and_boss_families_are_guardian_only(self):
  corrupt=apply_creature_world_policy("plushbound_guardian",{"prompt":"forest guardian","negative_prompt":""},creature_family="guardian_corrupt"); boss=apply_creature_world_policy("plushbound_guardian",{"prompt":"forest guardian","negative_prompt":""},creature_family="guardian_boss")
  self.assertEqual(corrupt["creature_family"],"guardian_corrupt"); self.assertIn("torn seams behave like wounds",corrupt["prompt"]); self.assertIn("cotton-like inner fiber",corrupt["prompt"])
  self.assertEqual(boss["creature_family"],"guardian_boss"); self.assertIn("large nonhuman creature anatomy",boss["prompt"]); self.assertIn("gorilla",boss["negative_prompt"])
  with self.assertRaises(ValueError): resolve_creature_family("plushbound_enemy","guardian_corrupt")
 def test_noncreature_presets_do_not_get_creature_language(self):
  base={"prompt":"adult traveler","negative_prompt":""}; out=apply_creature_world_policy("plushbound_character",base); self.assertFalse(out["creature_world_policy_applied"]); self.assertIsNone(out["creature_family"]); self.assertEqual(out["prompt"],base["prompt"])
 def test_input_not_mutated_and_unknown_family_fails_closed(self):
  base={"prompt":"guardian","negative_prompt":""}; apply_creature_world_policy("plushbound_guardian",base); self.assertNotIn("creature_family",base)
  with self.assertRaises(ValueError): apply_creature_world_policy("plushbound_guardian",base,creature_family="unknown")
if __name__=="__main__": unittest.main()
