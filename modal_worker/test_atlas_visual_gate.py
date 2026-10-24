import unittest

from atlas_visual_gate import CREATURE_CANARY_CASES, VISUAL_GATE_VERSION, record_creature_visual_review


class AtlasVisualGateTests(unittest.TestCase):
    def _judgments(self, passed=True):
        return {case_id: {"passed": passed, "reasons": [] if passed else ["visual defect"]} for case_id in CREATURE_CANARY_CASES}

    def test_all_cases_required_for_bounded_pass(self):
        review = record_creature_visual_review(
            workflow_run_id=123,
            head_sha="a" * 40,
            artifact_digest="sha256:" + "b" * 64,
            canary_version="canary-v1",
            judgments=self._judgments(True),
        )
        self.assertEqual(review["visual_gate_version"], VISUAL_GATE_VERSION)
        self.assertTrue(review["bounded_gate_passed"])
        self.assertEqual(len(review["passed_cases"]), 7)
        self.assertEqual(review["failed_cases"], [])
        self.assertFalse(review["automatic_full_production_authorized"])
        self.assertEqual(len(review["review_digest"]), 64)

    def test_one_failed_case_blocks_gate(self):
        judgments = self._judgments(True)
        judgments["guardian_boss_hexapod"] = {"passed": False, "reasons": ["only four legs visible"]}
        review = record_creature_visual_review(
            workflow_run_id=124,
            head_sha="c" * 40,
            artifact_digest="sha256:" + "d" * 64,
            canary_version="canary-v2",
            judgments=judgments,
        )
        self.assertFalse(review["bounded_gate_passed"])
        self.assertEqual(review["failed_cases"], ["guardian_boss_hexapod"])

    def test_missing_extra_and_reasonless_failures_fail_closed(self):
        judgments = self._judgments(True)
        judgments.pop("enemy_creature_hexapod")
        with self.assertRaisesRegex(ValueError, "case mismatch"):
            record_creature_visual_review(workflow_run_id=1, head_sha="a"*40, artifact_digest="sha256:"+"b"*64, canary_version="v", judgments=judgments)
        judgments = self._judgments(True)
        judgments["extra"] = {"passed": True, "reasons": []}
        with self.assertRaisesRegex(ValueError, "case mismatch"):
            record_creature_visual_review(workflow_run_id=1, head_sha="a"*40, artifact_digest="sha256:"+"b"*64, canary_version="v", judgments=judgments)
        judgments = self._judgments(True)
        judgments["enemy_creature_hexapod"] = {"passed": False, "reasons": []}
        with self.assertRaisesRegex(ValueError, "requires at least one reason"):
            record_creature_visual_review(workflow_run_id=1, head_sha="a"*40, artifact_digest="sha256:"+"b"*64, canary_version="v", judgments=judgments)


if __name__ == "__main__": unittest.main()
