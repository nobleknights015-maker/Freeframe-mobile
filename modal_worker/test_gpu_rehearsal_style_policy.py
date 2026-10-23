import unittest

from gpu_rehearsal_plan import GPU_REHEARSAL_VERSION, rehearsal_requests


class GPURehearsalStylePolicyTests(unittest.TestCase):
    def test_rehearsal_remains_exactly_32_assets(self):
        plan = rehearsal_requests()
        self.assertEqual(GPU_REHEARSAL_VERSION, "plushbound-gpu-rehearsal-v4")
        self.assertEqual(len(plan), 32)
        self.assertEqual(len({item["asset_id"] for item in plan}), 32)
        self.assertTrue(all(item["request"]["production_request_builder_version"] == "production-request-v2" for item in plan))

    def test_all_categories_use_validated_category_profiles(self):
        plan = rehearsal_requests()
        expected_profiles = {
            "plushbound_character": "plushbound_trinity",
            "plushbound_guardian": "plushbound_guardian_2d_candidate",
            "plushbound_enemy": "plushbound_trinity_creature",
            "plushbound_environment": "plushbound_trinity_environment",
        }
        self.assertEqual(len(plan), 32)

        for item in plan:
            request = item["request"]
            expected = expected_profiles[item["preset"]]
            self.assertTrue(request["production_style_validated"])
            self.assertEqual(request["production_style_profile"], expected)
            self.assertEqual(request["render_style_profile"], expected)
            self.assertIn("sharp", request["prompt"])
            if item["preset"] == "plushbound_guardian":
                self.assertTrue(request["guardian_composition_repair"])
                self.assertEqual(request["guardian_composition_version"], "guardian-single-view-v3")
                self.assertIn("one complete creature body visible exactly once", request["prompt"])
                self.assertIn("contact sheet", request["negative_prompt"])

    def test_character_requests_keep_full_length_composition_language(self):
        for item in rehearsal_requests():
            if item["preset"] == "plushbound_character":
                self.assertIn("single candid full-length scene", item["request"]["prompt"])


if __name__ == "__main__":
    unittest.main()
