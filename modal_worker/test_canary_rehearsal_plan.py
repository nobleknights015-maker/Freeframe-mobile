import unittest

from canary_rehearsal_plan import (
    CANARY_REHEARSAL_VERSION,
    CHARACTER_STYLE_LOCK_BLOCKER,
    canary_readiness,
    canary_requests,
)


class CanaryRehearsalPlanTests(unittest.TestCase):
    def test_canary_is_exactly_one_per_major_class(self):
        items = canary_requests()
        self.assertEqual(CANARY_REHEARSAL_VERSION, "plushbound-canary-v2")
        self.assertEqual(len(items), 4)
        self.assertEqual(
            {item["preset"] for item in items},
            {"plushbound_character", "plushbound_guardian", "plushbound_enemy", "plushbound_environment"},
        )
        self.assertEqual(len({item["request"]["seed"] for item in items}), 4)

    def test_canary_fails_closed_without_character_style_lock(self):
        readiness = canary_readiness()
        self.assertFalse(readiness["full_production_authorized"])
        self.assertFalse(readiness["character_style_lock_ready"])
        self.assertIn(CHARACTER_STYLE_LOCK_BLOCKER, readiness["blocked_presets"])
        self.assertFalse(readiness["ready_for_four_gpu_canary"])

    def test_style_lock_alone_does_not_bypass_unvalidated_asset_classes(self):
        readiness = canary_readiness(character_style_lock_ready=True)
        self.assertTrue(readiness["character_style_lock_ready"])
        self.assertNotIn(CHARACTER_STYLE_LOCK_BLOCKER, readiness["blocked_presets"])
        if readiness["blocked_presets"]:
            self.assertFalse(readiness["ready_for_four_gpu_canary"])


if __name__ == "__main__":
    unittest.main()
