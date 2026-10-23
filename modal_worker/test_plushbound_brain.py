import unittest
from plushbound_brain import BRAIN_VERSION,FAMILY_CONTRACTS,brain_snapshot,get_family_contract,missing_context
class PlushboundBrainTests(unittest.TestCase):
 def test_snapshot_is_fail_closed_and_contains_core_families(self):
  snap=brain_snapshot(); self.assertEqual(snap["brain_version"],BRAIN_VERSION); self.assertEqual(snap["world"],"Plushtopia"); self.assertFalse(snap["automatic_full_production_authorized"])
  for family in ("guardian_friendly","guardian_corrupt","guardian_boss","enemy_creature","enemy_human","environment_master","mv_single_character","tileset_48px","audio"): self.assertIn(family,snap["families"])
 def test_creature_families_share_renderer_contract(self):
  for family in ("guardian_friendly","guardian_corrupt","guardian_boss"):
   c=get_family_contract(family); self.assertEqual(c.production_preset,"plushbound_guardian"); self.assertEqual(c.creature_family,family)
  e=get_family_contract("enemy_creature"); self.assertEqual(e.production_preset,"plushbound_enemy"); self.assertEqual(e.creature_family,"enemy_creature")
 def test_human_enemy_requires_lore_context(self):
  self.assertEqual(missing_context("enemy_human",{"region":"Elyndor"}),["faction","role","guardian_relationship"])
 def test_specialized_families_do_not_pretend_to_be_generation_ready(self):
  for family in ("creator_layer","tileset_48px","guardian_walk_sheet","audio"): self.assertIsNone(FAMILY_CONTRACTS[family].production_preset)
 def test_unknown_family_rejected(self):
  with self.assertRaises(ValueError): get_family_contract("missing")
if __name__=="__main__": unittest.main()
