import unittest

from character_style_lock import (
    STYLE_LOCK_VERSION,
    CharacterStyleLockReceipt,
    evaluate_character_style_lock,
)
from production_style_policy import PRODUCTION_STYLE_POLICY_VERSION, style_for_preset
from style_profiles import STYLE_PROFILE_VERSION


class CharacterStyleLockTests(unittest.TestCase):
    def valid_receipt(self, **overrides):
        values = {
            "approved": True,
            "reviewer": "explicit-visual-qa",
            "benchmark_sha256": "a" * 64,
            "profile": style_for_preset("plushbound_character"),
            "profile_version": STYLE_PROFILE_VERSION,
            "policy_version": PRODUCTION_STYLE_POLICY_VERSION,
            "note": "reviewed bounded benchmark",
        }
        values.update(overrides)
        return CharacterStyleLockReceipt(**values)

    def test_missing_receipt_fails_closed(self):
        result = evaluate_character_style_lock(None)
        self.assertEqual(result["version"], STYLE_LOCK_VERSION)
        self.assertFalse(result["ready"])
        self.assertFalse(result["full_production_authorized"])

    def test_current_evidence_receipt_can_unlock_only_canary_prerequisite(self):
        result = evaluate_character_style_lock(self.valid_receipt())
        self.assertTrue(result["ready"])
        self.assertFalse(result["full_production_authorized"])

    def test_stale_profile_or_policy_is_rejected(self):
        self.assertFalse(evaluate_character_style_lock(self.valid_receipt(profile_version="old"))["ready"])
        self.assertFalse(evaluate_character_style_lock(self.valid_receipt(policy_version="old"))["ready"])

    def test_bad_hash_unapproved_or_missing_reviewer_is_rejected(self):
        self.assertFalse(evaluate_character_style_lock(self.valid_receipt(benchmark_sha256="bad"))["ready"])
        self.assertFalse(evaluate_character_style_lock(self.valid_receipt(approved=False))["ready"])
        self.assertFalse(evaluate_character_style_lock(self.valid_receipt(reviewer="   "))["ready"])


if __name__ == "__main__":
    unittest.main()
