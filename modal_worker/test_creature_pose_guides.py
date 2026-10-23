import unittest
from creature_pose_guides import POSE_GUIDE_VERSION,build_pose_guide

class CreaturePoseGuideTests(unittest.TestCase):
 def test_all_creature_families_get_project_owned_procedural_guides(self):
  for family in ("guardian_friendly","guardian_corrupt","guardian_boss","enemy_creature"):
   image=build_pose_guide(family); self.assertEqual(image.size,(512,512)); self.assertEqual(image.mode,"RGB"); self.assertEqual(POSE_GUIDE_VERSION,"creature-pose-guide-v1"); self.assertIn((0,0,0),set(image.getdata())); self.assertIn((255,255,255),set(image.getdata()))
 def test_custom_size_is_supported(self): self.assertEqual(build_pose_guide("guardian_boss",256).size,(256,256))
 def test_invalid_family_and_size_fail_closed(self):
  with self.assertRaises(ValueError): build_pose_guide("missing")
  with self.assertRaises(ValueError): build_pose_guide("guardian_friendly",64)
if __name__=="__main__": unittest.main()
