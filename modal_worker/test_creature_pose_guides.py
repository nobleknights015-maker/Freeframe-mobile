import unittest
from creature_pose_guides import POSE_GUIDE_VERSION, build_pose_guide


class CreaturePoseGuideTests(unittest.TestCase):
    def test_all_creature_families_get_project_owned_exterior_guides(self):
        for family in ("guardian_friendly","guardian_corrupt","guardian_boss","enemy_creature"):
            image=build_pose_guide(family)
            self.assertEqual(image.size,(512,512))
            self.assertEqual(image.mode,"RGB")
            self.assertEqual(POSE_GUIDE_VERSION,"creature-pose-guide-v3-exterior-silhouette")
            self.assertIn((0,0,0),set(image.getdata()))
            self.assertIn((255,255,255),set(image.getdata()))

    def test_friendly_variants_cover_diverse_body_plans(self):
        variants=("quadruped","winged","biped","long_low")
        images=[build_pose_guide("guardian_friendly",variant=v) for v in variants]
        self.assertEqual(len(images),4)
        self.assertEqual(len({image.tobytes() for image in images}),4)

    def test_hexapod_guides_are_distinct_from_quadruped_and_each_other(self):
        boss=build_pose_guide("guardian_boss",variant="hexapod")
        enemy=build_pose_guide("enemy_creature",variant="hexapod")
        quad=build_pose_guide("guardian_friendly",variant="quadruped")
        self.assertNotEqual(boss.tobytes(),quad.tobytes())
        self.assertNotEqual(enemy.tobytes(),quad.tobytes())
        self.assertNotEqual(boss.tobytes(),enemy.tobytes())

    def test_custom_size_is_supported(self):
        self.assertEqual(build_pose_guide("guardian_boss",256).size,(256,256))

    def test_invalid_family_variant_and_size_fail_closed(self):
        with self.assertRaises(ValueError): build_pose_guide("missing")
        with self.assertRaises(ValueError): build_pose_guide("guardian_friendly",64)
        with self.assertRaises(ValueError): build_pose_guide("guardian_friendly",variant="missing")
        with self.assertRaises(ValueError): build_pose_guide("enemy_creature",variant="quadruped")


if __name__=="__main__": unittest.main()
