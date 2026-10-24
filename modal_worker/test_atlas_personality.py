import unittest

from atlas_personality import ATLAS_PERSONALITY_VERSION, PERSONALITY, personality_snapshot, speak, speak_from_request


class AtlasPersonalityTests(unittest.TestCase):
    def test_snapshot_exposes_canonical_identity_and_hard_boundaries(self):
        snapshot = personality_snapshot()
        self.assertEqual(snapshot["personality_version"], ATLAS_PERSONALITY_VERSION)
        self.assertEqual(snapshot["personality"]["name"], "Atlas")
        boundaries = snapshot["personality"]["hard_boundaries"]
        self.assertTrue(boundaries["presentation_only"])
        self.assertFalse(boundaries["may_direct_vera"])
        self.assertFalse(boundaries["may_condition_vera"])
        self.assertFalse(boundaries["may_change_production_rules"])
        self.assertFalse(boundaries["may_override_geometry_or_manifest_rules"])

    def test_plan_ready_voice_is_atlas_and_presentation_only(self):
        result = speak("plan_ready", subject="guardian atlas")
        self.assertEqual(result["speaker"], "Atlas")
        self.assertIn("mapped out", result["text"])
        self.assertTrue(result["presentation_only"])
        self.assertFalse(result["authority_changed"])

    def test_qa_events_have_distinct_voice(self):
        retry = speak("retry", subject="sprite sheet", retry_count=2)
        rejected = speak("rejected", subject="sprite sheet")
        blocked = speak("blocked", subject="sprite sheet")
        self.assertIn("Retry 2", retry["text"])
        self.assertIn("Nope", rejected["text"])
        self.assertIn("not forcing it past a gate", blocked["text"])

    def test_request_adapter_is_deterministic(self):
        request = {"event": "accepted", "subject": "Elyndor NPC sheet"}
        self.assertEqual(speak_from_request(request), speak_from_request(request))

    def test_personality_cannot_impersonate_other_roles(self):
        boundaries = PERSONALITY["hard_boundaries"]
        self.assertFalse(boundaries["may_impersonate_jarvis"])
        self.assertFalse(boundaries["may_impersonate_vera"])


if __name__ == "__main__":
    unittest.main()
