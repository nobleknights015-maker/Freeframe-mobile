import unittest

from guardian_composition_policy import (
    GUARDIAN_COMPOSITION_VERSION,
    apply_guardian_composition,
)
from production_presets import get_preset


class GuardianCompositionPolicyTests(unittest.TestCase):
    def test_repair_preserves_subject_and_dimensions(self):
        base = get_preset("plushbound_guardian").apply(
            "small foxlike Plush Guardian with stitched ears", seed=33
        )
        repaired = apply_guardian_composition(base)
        self.assertTrue(repaired["prompt"].startswith("small foxlike Plush Guardian"))
        self.assertIn("exactly one creature", repaired["prompt"])
        self.assertIn("one camera view", repaired["prompt"])
        self.assertIn("one continuous scene", repaired["prompt"])
        self.assertIn("front side back views", repaired["negative_prompt"])
        self.assertEqual(repaired["width"], base["width"])
        self.assertEqual(repaired["height"], base["height"])
        self.assertEqual(repaired["seed"], 33)
        self.assertTrue(repaired["guardian_composition_repair"])
        self.assertEqual(
            repaired["guardian_composition_version"], GUARDIAN_COMPOSITION_VERSION
        )

    def test_input_not_mutated(self):
        base = get_preset("plushbound_guardian").apply("small plush guardian", seed=7)
        original_prompt = base["prompt"]
        apply_guardian_composition(base)
        self.assertEqual(base["prompt"], original_prompt)
        self.assertNotIn("guardian_composition_repair", base)

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            apply_guardian_composition({"prompt": "   ", "negative_prompt": ""})


if __name__ == "__main__":
    unittest.main()
