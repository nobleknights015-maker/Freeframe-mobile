import unittest

from creature_structure_conditioning import (
    CREATURE_STRUCTURE_CONDITIONING_VERSION,
    CONTROL_PROMPT,
    build_conditioning,
    infer_pose_variant,
)
from creature_pose_guides import POSE_GUIDE_VERSION, build_pose_guide


class CreatureStructureConditioningTests(unittest.TestCase):
    def test_pose_variant_inference_is_generator_side_and_body_plan_aware(self):
        self.assertEqual(infer_pose_variant("guardian_friendly", "small four-legged meadow species"), "quadruped")
        self.assertEqual(infer_pose_variant("guardian_friendly", "winged Guardian in flight"), "winged")
        self.assertEqual(infer_pose_variant("guardian_friendly", "small biped Guardian"), "biped")
        self.assertEqual(infer_pose_variant("guardian_friendly", "long low Guardian"), "long_low")
        self.assertEqual(infer_pose_variant("guardian_corrupt", "damaged low creature"), "low_quadruped")
        self.assertEqual(infer_pose_variant("guardian_boss", "ancient boss"), "hexapod")
        self.assertEqual(infer_pose_variant("enemy_creature", "low four-legged prowler"), "quadruped")
        self.assertEqual(infer_pose_variant("enemy_creature", "exactly six weight-bearing legs"), "hexapod")

    def test_enemy_quadruped_guide_is_supported(self):
        image = build_pose_guide("enemy_creature", size=512, variant="quadruped")
        self.assertEqual(image.size, (512, 512))
        self.assertEqual(image.mode, "RGB")
        self.assertIn("enemy-quadruped", POSE_GUIDE_VERSION)

    def test_project_owned_style_plus_pose_conditioning_builds(self):
        style, pose, control, metadata = build_conditioning(
            "guardian_friendly",
            "small four-legged meadow Guardian",
            size=512,
        )
        self.assertEqual(style.mode, "RGB")
        self.assertEqual(pose.mode, "RGB")
        self.assertEqual(metadata.conditioning_version, CREATURE_STRUCTURE_CONDITIONING_VERSION)
        self.assertEqual(metadata.style_anchor_ownership, "project_owned")
        self.assertEqual(metadata.pose_variant, "quadruped")
        self.assertEqual(len(metadata.style_anchor_sha256), 64)
        self.assertIn("Reference image 1 is a validated Plushbound creature-family reference", control)
        self.assertIn("Reference image 2 is a plain black exterior silhouette", control)
        self.assertEqual(control, CONTROL_PROMPT)

    def test_unknown_family_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "unsupported creature conditioning family"):
            infer_pose_variant("unknown", "creature")


if __name__ == "__main__":
    unittest.main()
