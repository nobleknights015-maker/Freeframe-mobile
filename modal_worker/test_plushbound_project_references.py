import unittest
from plushbound_project_references import REFERENCES,REFERENCE_LIBRARY_VERSION,get_project_reference,reference_snapshot

class ProjectReferenceTests(unittest.TestCase):
 def test_all_four_creature_families_have_project_owned_refs(self):
  self.assertEqual(set(REFERENCES),{"guardian_friendly","guardian_corrupt","guardian_boss","enemy_creature"})
  for family in REFERENCES:
   ref=get_project_reference(family); self.assertEqual(ref.ownership,"project_owned"); self.assertEqual(ref.purpose,"visual_conditioning_only"); self.assertTrue(ref.path.is_file()); self.assertEqual(len(ref.sha256),64)
 def test_reference_pixels_decode_and_are_small_conditioning_crops(self):
  for family in REFERENCES:
   image=get_project_reference(family).load_image(); self.assertEqual(image.mode,"RGB"); self.assertLessEqual(image.width,128); self.assertLessEqual(image.height,128); self.assertGreater(image.width,32); self.assertGreater(image.height,32)
 def test_snapshot_never_authorizes_production(self):
  snap=reference_snapshot(); self.assertEqual(snap["library_version"],REFERENCE_LIBRARY_VERSION); self.assertFalse(snap["production_authorized"])
 def test_unknown_family_fails_closed(self):
  with self.assertRaises(ValueError): get_project_reference("missing")
if __name__=="__main__": unittest.main()
