import unittest

from canary_rehearsal_plan import (
    CANARY_REHEARSAL_VERSION,
    CHARACTER_STYLE_LOCK_BLOCKER,
    canary_readiness,
    canary_requests,
)
from character_style_lock import CharacterStyleLockReceipt
from production_style_policy import PRODUCTION_STYLE_POLICY_VERSION, style_for_preset
from style_profiles import STYLE_PROFILE_VERSION


class CanaryRehearsalPlanTests(unittest.TestCase):
    def valid_style_lock(self):
        return CharacterStyleLockReceipt(
            approved=True,
            reviewer="explicit-visual-qa",
            benchmark_sha256="a" * 64,
            profile=style_for_preset("plushbound_character"),
            profile_version=STYLE_PROFILE_VERSION,
            policy_version=PRODUCTION_STYLE_POLICY_VERSION,
            note="reviewed bounded benchmark",
        )

    def test_canary_is_exactly_one_per_major_class(self):
        items = canary_requests()
        self.assertEqual(CANARY_REHEARSAL_VERSION, "plushbound-canary-v3")
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

    def test_valid_evidence_receipt_satisfies_style_lock_prerequisite(self):
        readiness = canary_readiness(character_style_lock=self.valid_style_lock())
        self.assertTrue(readiness["character_style_lock_ready"])
        self.assertNotIn(CHARACTER_STYLE_LOCK_BLOCKER, readiness["blocked_presets"])
        self.assertFalse(readiness["full_production_authorized"])
        if not readiness["blocked_presets"]:
            self.assertTrue(readiness["ready_for_four_gpu_canary"])

    def test_stale_receipt_does_not_unlock_canary(self):
        stale = self.valid_style_lock()
        stale = CharacterStyleLockReceipt(
            approved=stale.approved,
            reviewer=stale.reviewer,
            benchmark_sha256=stale.benchmark_sha256,
            profile=stale.profile,
            profile_version="old-profile-version",
            policy_version=stale.policy_version,
            note=stale.note,
        )
        readiness = canary_readiness(character_style_lock=stale)
        self.assertFalse(readiness["character_style_lock_ready"])
        self.assertIn(CHARACTER_STYLE_LOCK_BLOCKER, readiness["blocked_presets"])
        self.assertFalse(readiness["ready_for_four_gpu_canary"])


if __name__ == "__main__":
    unittest.main()
