import unittest
from production_presets import PLUSHBOUND_STYLE_VERSION,PRESETS,get_preset
class ProductionPresetTests(unittest.TestCase):
 def test_all_presets_build_valid_requests(self):
  for name,preset in PRESETS.items():
   request=preset.apply("silver-haired traveler with a small satchel",seed=42); self.assertEqual(request["style_preset"],name); self.assertEqual(request["style_version"],PLUSHBOUND_STYLE_VERSION); self.assertIn("malformed anatomy",request["negative_prompt"]); self.assertEqual(request["width"]%8,0); self.assertGreaterEqual(request["steps"],20)
 def test_v34_identity_is_current(self): self.assertEqual(PLUSHBOUND_STYLE_VERSION,"v3.4")
 def test_character_uses_scene_composition_not_sheet_language(self):
  r=get_preset("plushbound_character").apply("adult traveler",seed=1); self.assertIn("single candid full-length scene",r["prompt"]); self.assertIn("presentation board",r["negative_prompt"])
 def test_enemy_uses_horizontal_quadruped_and_textile_biology(self):
  r=get_preset("plushbound_enemy").apply("mossback woodland prowler",seed=2); self.assertIn("animal spine parallel to the ground",r["prompt"]); self.assertIn("living textile organism",r["prompt"]); self.assertIn("woven felt quilted or thread-based hide",r["prompt"]); self.assertIn("ordinary flesh-and-fur animal",r["negative_prompt"])
 def test_guardian_is_living_species_and_blocks_retail_toy(self):
  r=get_preset("plushbound_guardian").apply("foxlike guardian",seed=3); self.assertIn("living fantasy companion species",r["prompt"]); self.assertIn("creature first and textile second",r["prompt"]); self.assertIn("retail plush toy",r["negative_prompt"])
 def test_environment_keeps_existing_semantics(self): self.assertIn("Outdoor landscape only",get_preset("plushbound_environment").apply("sunny plains",seed=4)["prompt"])
 def test_unknown_preset_rejected(self):
  with self.assertRaises(ValueError): get_preset("missing")
 def test_empty_prompt_rejected(self):
  with self.assertRaises(ValueError): get_preset("plushbound_guardian").apply("   ",seed=1)
if __name__=="__main__": unittest.main()
