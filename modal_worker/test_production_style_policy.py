import unittest
from production_presets import get_preset
from production_style_policy import PRODUCTION_STYLE_POLICY_VERSION,apply_production_style,style_for_preset
class ProductionStylePolicyTests(unittest.TestCase):
 def test_validated_presets_use_category_specific_styles(self):
  cases=(("plushbound_character","adult traveler","plushbound_trinity"),("plushbound_guardian","small foxlike guardian","plushbound_guardian_2d_candidate"),("plushbound_enemy","quadruped forest beast","plushbound_trinity_creature"),("plushbound_environment","sunny plains","plushbound_trinity_environment"))
  for preset,prompt,expected in cases:
   styled=apply_production_style(preset,get_preset(preset).apply(prompt,seed=7)); self.assertEqual(style_for_preset(preset),expected); self.assertTrue(styled["production_style_validated"]); self.assertEqual(styled["production_style_profile"],expected); self.assertEqual(styled["production_style_policy_version"],PRODUCTION_STYLE_POLICY_VERSION)
 def test_guardian_style_is_alive_textile_creature_not_product(self):
  styled=apply_production_style("plushbound_guardian",get_preset("plushbound_guardian").apply("guardian",seed=9)); self.assertIn("unmistakably alive and behaving as a fantasy species",styled["prompt"]); self.assertIn("matte woven textile dermis",styled["prompt"]); self.assertIn("natural creature eyes",styled["prompt"]); self.assertIn("retail plush toy",styled["negative_prompt"]); self.assertIn("realistic fur coat",styled["negative_prompt"])
 def test_enemy_style_requires_textile_species(self):
  styled=apply_production_style("plushbound_enemy",get_preset("plushbound_enemy").apply("prowler",seed=10)); self.assertIn("living Plushtopia species",styled["prompt"]); self.assertIn("creature first and textile biology second",styled["prompt"]); self.assertIn("visibly woven quilted or layered textile dermis",styled["prompt"]); self.assertIn("ordinary flesh-and-fur animal",styled["negative_prompt"])
 def test_unknown_preset_fails_closed(self):
  styled=apply_production_style("unknown",{"prompt":"test","negative_prompt":""}); self.assertFalse(styled["production_style_validated"]); self.assertIsNone(styled["production_style_profile"])
if __name__=="__main__": unittest.main()
