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
        self.assertIn("single-view 2D illustrated", repaired["prompt"])
        self.assertIn("one continuous outdoor background", repaired["prompt"])
        self.assertIn("one complete creature body visible exactly once", repaired["prompt"])
        self.assertIn("rather than a photographed toy", repaired["prompt"])
        self.assertIn("no model-sheet arrangement", repaired["prompt"])
        self.assertIn("contact sheet", repaired["negative_prompt"])
        self.assertIn("front side back views", repaired["negative_prompt"])
        self.assertEqual(repaired["width"], base["width"])
        self.assertEqual(repaired["height"], base["height"])
        self.assertEqual(repaired["seed"], 33)
        self.assertTrue(repaired["guardian_composition_repair"])
        self.assertEqual(GUARDIAN_COMPOSITION_VERSION, "guardian-single-view-v3")
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
