import unittest

from gpu_rehearsal_plan import GPU_REHEARSAL_VERSION, rehearsal_requests


class GPURehearsalStylePolicyTests(unittest.TestCase):
    def test_rehearsal_remains_exactly_32_assets(self):
        plan = rehearsal_requests()
        self.assertEqual(GPU_REHEARSAL_VERSION, "plushbound-gpu-rehearsal-v2")
        self.assertEqual(len(plan), 32)
        self.assertEqual(len({item["asset_id"] for item in plan}), 32)

    def test_validated_categories_use_trinity_guardian_stays_unstyled(self):
        plan = rehearsal_requests()
        validated = [
            item for item in plan
            if item["preset"] in {"plushbound_character", "plushbound_enemy", "plushbound_environment"}
        ]
        guardians = [item for item in plan if item["preset"] == "plushbound_guardian"]
        self.assertEqual(len(validated), 24)
        self.assertEqual(len(guardians), 8)

        for item in validated:
            request = item["request"]
            self.assertTrue(request["production_style_validated"])
            self.assertEqual(request["production_style_profile"], "plushbound_trinity")
            self.assertEqual(request["render_style_profile"], "plushbound_trinity")
            self.assertIn("bright modern fantasy JRPG key art", request["prompt"])

        for item in guardians:
            request = item["request"]
            self.assertFalse(request["production_style_validated"])
            self.assertIsNone(request["production_style_profile"])
            self.assertNotIn("render_style_profile", request)

    def test_character_requests_keep_full_length_composition_language(self):
        for item in rehearsal_requests():
            if item["preset"] == "plushbound_character":
                self.assertIn("single candid full-length scene", item["request"]["prompt"])


if __name__ == "__main__":
    unittest.main()
