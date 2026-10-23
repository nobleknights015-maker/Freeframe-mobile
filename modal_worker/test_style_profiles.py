import unittest
from style_profiles import STYLE_PROFILE_VERSION,STYLE_PROFILES,get_style_profile
class StyleProfileTests(unittest.TestCase):
 def test_profiles_apply_without_mutating_input(self):
  base={"prompt":"adult fantasy traveler. A single candid full-length scene containing one adult traveler","negative_prompt":"text, watermark","width":768,"height":1024,"seed":42}
  for name,profile in STYLE_PROFILES.items():
   applied=profile.apply(base); self.assertEqual(applied["render_style_profile"],name); self.assertEqual(applied["render_style_version"],STYLE_PROFILE_VERSION); self.assertTrue(applied["prompt"].startswith("adult fantasy traveler. ")); self.assertTrue(applied["negative_prompt"].startswith(profile.negative)); self.assertIn("watercolor haze",applied["negative_prompt"])
 def test_trinity_character_keeps_contemporary_jrpg_target(self):
  text=get_style_profile("plushbound_trinity").positive; self.assertIn("premium contemporary fantasy JRPG character key-art illustration",text); self.assertIn("sharp high-detail digital finish",text)
 def test_environment_is_modern_without_poster_cues(self):
  text=get_style_profile("plushbound_trinity_environment").positive; self.assertIn("premium contemporary fantasy JRPG environment key art",text); self.assertIn("no foreground hero",text)
 def test_guardian_is_living_creature_not_product_plush(self):
  p=get_style_profile("plushbound_guardian_2d_candidate"); self.assertIn("Guardian-creature key art",p.positive); self.assertIn("unmistakably alive and behaving as a fantasy species",p.positive); self.assertIn("matte woven textile dermis",p.positive); self.assertIn("natural creature eyes",p.positive); self.assertIn("retail plush toy",p.negative); self.assertIn("fuzzy synthetic plush pile",p.negative); self.assertIn("realistic fur coat",p.negative)
 def test_enemy_is_textile_creature_not_ordinary_animal(self):
  p=get_style_profile("plushbound_trinity_creature"); self.assertIn("living Plushtopia species",p.positive); self.assertIn("creature first and textile biology second",p.positive); self.assertIn("visibly woven quilted or layered textile dermis",p.positive); self.assertIn("sparse thread bristles instead of ordinary fur",p.positive); self.assertIn("ordinary flesh-and-fur animal",p.negative); self.assertIn("realistic fur coat",p.negative)
 def test_profiles_are_visually_distinct(self): self.assertEqual(len({p.positive for p in STYLE_PROFILES.values()}),len(STYLE_PROFILES))
 def test_empty_prompt_rejected(self):
  with self.assertRaises(ValueError): get_style_profile("plushbound_mv").apply({"prompt":"   "})
 def test_unknown_profile_rejected(self):
  with self.assertRaises(ValueError): get_style_profile("missing")
if __name__=="__main__": unittest.main()
