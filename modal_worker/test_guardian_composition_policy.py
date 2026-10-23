import unittest
from guardian_composition_policy import GUARDIAN_COMPOSITION_VERSION,apply_guardian_composition
from production_presets import get_preset
class GuardianCompositionPolicyTests(unittest.TestCase):
 def test_repair_preserves_subject_and_dimensions(self):
  base=get_preset("plushbound_guardian").apply("small foxlike Plush Guardian with stitched ears",seed=33); repaired=apply_guardian_composition(base)
  self.assertTrue(repaired["prompt"].startswith("small foxlike Plush Guardian")); self.assertIn("one complete creature body visible exactly once",repaired["prompt"]); self.assertIn("weight-bearing limbs",repaired["prompt"]); self.assertIn("candid creature behavior rather than object display",repaired["prompt"]); self.assertIn("retail plush toy",repaired["negative_prompt"]); self.assertEqual(repaired["width"],base["width"]); self.assertEqual(GUARDIAN_COMPOSITION_VERSION,"guardian-single-view-v4")
 def test_input_not_mutated(self):
  base=get_preset("plushbound_guardian").apply("small plush guardian",seed=7); old=base["prompt"]; apply_guardian_composition(base); self.assertEqual(base["prompt"],old); self.assertNotIn("guardian_composition_repair",base)
 def test_empty_prompt_rejected(self):
  with self.assertRaises(ValueError): apply_guardian_composition({"prompt":"   ","negative_prompt":""})
if __name__=="__main__": unittest.main()
