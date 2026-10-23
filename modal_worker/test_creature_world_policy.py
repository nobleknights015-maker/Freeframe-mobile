import unittest
from creature_world_policy import CREATURE_WORLD_POLICY_VERSION, apply_creature_world_policy, resolve_creature_family

class CreatureWorldPolicyTests(unittest.TestCase):
 def test_guardian_defaults_to_friendly_living_fabric(self):
  base={"prompt":"small meadow companion. one creature","negative_prompt":"text"}; out=apply_creature_world_policy("plushbound_guardian",base)
  self.assertTrue(out["creature_world_policy_applied"]); self.assertEqual(out["creature_family"],"guardian_friendly"); self.assertEqual(out["creature_world_policy_version"],CREATURE_WORLD_POLICY_VERSION)
  self.assertIn("living organism native to Plushtopia",out["prompt"]); self.assertIn("creature first and textile second",out["prompt"]); self.assertIn("not a toy doll or manufactured object",out["prompt"]); self.assertIn("retail plush toy",out["negative_prompt"]); self.assertIn("ordinary flesh-and-fur animal",out["negative_prompt"])
 def test_enemy_forces_living_textile_ecosystem(self):
  out=apply_creature_world_policy("plushbound_enemy",{"prompt":"forest prowler","negative_prompt":""}); self.assertEqual(out["creature_family"],"enemy_creature"); self.assertIn("wild hostile Plushtopia creature",out["prompt"]); self.assertIn("woven felt or quilted hide",out["prompt"]); self.assertIn("normal wolf",out["negative_prompt"])
 def test_corrupt_and_boss_families_are_guardian_only(self):
  for family in ("guardian_corrupt","guardian_boss"):
   out=apply_creature_world_policy("plushbound_guardian",{"prompt":"forest guardian","negative_prompt":""},creature_family=family); self.assertEqual(out["creature_family"],family)
  with self.assertRaises(ValueError): resolve_creature_family("plushbound_enemy","guardian_corrupt")
 def test_noncreature_presets_do_not_get_creature_language(self):
  base={"prompt":"adult traveler","negative_prompt":""}; out=apply_creature_world_policy("plushbound_character",base); self.assertFalse(out["creature_world_policy_applied"]); self.assertIsNone(out["creature_family"]); self.assertEqual(out["prompt"],base["prompt"])
 def test_input_not_mutated_and_unknown_family_fails_closed(self):
  base={"prompt":"guardian","negative_prompt":""}; apply_creature_world_policy("plushbound_guardian",base); self.assertNotIn("creature_family",base)
  with self.assertRaises(ValueError): apply_creature_world_policy("plushbound_guardian",base,creature_family="unknown")
if __name__=="__main__": unittest.main()
