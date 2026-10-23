import unittest
from guardian_composition_policy import GUARDIAN_COMPOSITION_VERSION,apply_guardian_composition
from production_presets import get_preset
class GuardianCompositionPolicyTests(unittest.TestCase):
 def test_family_specific_composition_is_applied(self):
  base=get_preset("plushbound_guardian").apply("woodland Guardian",seed=33)
  friendly=apply_guardian_composition(base,creature_family="guardian_friendly"); corrupt=apply_guardian_composition(base,creature_family="guardian_corrupt"); boss=apply_guardian_composition(base,creature_family="guardian_boss")
  self.assertEqual(GUARDIAN_COMPOSITION_VERSION,"guardian-family-composition-v5"); self.assertIn("small-to-medium companion creature",friendly["prompt"]); self.assertIn("hostile corrupted Guardian",corrupt["prompt"]); self.assertIn("large imposing nonhuman Guardian boss",boss["prompt"]); self.assertIn("gorilla",boss["negative_prompt"])
  self.assertEqual(friendly["guardian_composition_family"],"guardian_friendly"); self.assertEqual(corrupt["guardian_composition_family"],"guardian_corrupt"); self.assertEqual(boss["guardian_composition_family"],"guardian_boss")
 def test_input_not_mutated(self):
  base=get_preset("plushbound_guardian").apply("small guardian",seed=7); old=base["prompt"]; apply_guardian_composition(base); self.assertEqual(base["prompt"],old); self.assertNotIn("guardian_composition_repair",base)
 def test_invalid_family_and_empty_prompt_rejected(self):
  with self.assertRaises(ValueError): apply_guardian_composition({"prompt":"guardian"},creature_family="missing")
  with self.assertRaises(ValueError): apply_guardian_composition({"prompt":"   ","negative_prompt":""})
if __name__=="__main__": unittest.main()
