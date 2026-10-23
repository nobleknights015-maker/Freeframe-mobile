import unittest

from gpu_rehearsal_plan import GPU_REHEARSAL_VERSION, rehearsal_requests


class GPURehearsalStylePolicyTests(unittest.TestCase):
    def test_rehearsal_remains_exactly_32_assets(self):
        plan = rehearsal_requests()
        self.assertEqual(GPU_REHEARSAL_VERSION, "plushbound-gpu-rehearsal-v2")
        self.assertEqual(len(plan), 32)
        self.assertEqual(len({item["asset_id"] for item in plan}), 32)

    def test_only_character_requests_use_validated_trinity_style(self):
        plan = rehearsal_requests()
        characters = [item for item in plan if item["preset"] == "plushbound_character"]
        others = [item for item in plan if item["preset"] != "plushbound_character"]
        self.assertEqual(len(characters), 8)
        self.assertEqual(len(others), 24)

        for item in characters:
            request = item["request"]
            self.assertTrue(request["production_style_validated"])
            self.assertEqual(request["production_style_profile"], "plushbound_trinity")
            self.assertEqual(request["render_style_profile"], "plushbound_trinity")
            self.assertIn("bright modern fantasy JRPG key art", request["prompt"])
            self.assertIn("single candid full-length scene", request["prompt"])

        for item in others:
            request = item["request"]
            self.assertFalse(request["production_style_validated"])
            self.assertIsNone(request["production_style_profile"])
            self.assertNotIn("render_style_profile", request)


if __name__ == "__main__":
    unittest.main()
