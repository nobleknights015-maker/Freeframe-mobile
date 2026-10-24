import unittest

from atlas_visual_gate import (
    CREATURE_CANARY_CASES,
    MASTER_CANARY_CASES,
    VISUAL_GATE_VERSION,
    record_creature_visual_review,
    record_master_visual_review,
)


class AtlasVisualGateTests(unittest.TestCase):
    @staticmethod
    def _judgments(cases, passed=True):
        return {case_id: {"passed": passed, "reasons": [] if passed else ["visual defect"]} for case_id in cases}

    def test_all_creature_cases_required_for_bounded_pass(self):
        review = record_creature_visual_review(
            workflow_run_id=123,
            head_sha="a" * 40,
            artifact_digest="sha256:" + "b" * 64,
            canary_version="canary-v1",
            judgments=self._judgments(CREATURE_CANARY_CASES, True),
        )
        self.assertEqual(review["visual_gate_version"], VISUAL_GATE_VERSION)
        self.assertTrue(review["bounded_gate_passed"])
        self.assertEqual(len(review["passed_cases"]), 7)
        self.assertEqual(review["failed_cases"], [])
        self.assertFalse(review["automatic_full_production_authorized"])
        self.assertFalse(review["catalog_wide_launch_authorized"])
        self.assertEqual(len(review["review_digest"]), 64)

    def test_one_failed_creature_case_blocks_gate(self):
        judgments = self._judgments(CREATURE_CANARY_CASES, True)
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

    def test_master_matrix_requires_all_four_lanes(self):
        review = record_master_visual_review(
            workflow_run_id=200,
            head_sha="e" * 40,
            artifact_digest="sha256:" + "f" * 64,
            canary_version="matrix-v1",
            judgments=self._judgments(MASTER_CANARY_CASES, True),
        )
        self.assertTrue(review["bounded_gate_passed"])
        self.assertEqual(review["required_cases"], list(MASTER_CANARY_CASES))
        self.assertEqual(review["scope"], "bounded four-lane generated-master visual canary")
        self.assertFalse(review["automatic_full_production_authorized"])
        self.assertFalse(review["catalog_wide_launch_authorized"])

    def test_failed_master_lane_blocks_gate(self):
        judgments = self._judgments(MASTER_CANARY_CASES, True)
        judgments["environment_elyndor_road"] = {"passed": False, "reasons": ["foreground character present"]}
        review = record_master_visual_review(
            workflow_run_id=201,
            head_sha="1" * 40,
            artifact_digest="sha256:" + "2" * 64,
            canary_version="matrix-v2",
            judgments=judgments,
        )
        self.assertFalse(review["bounded_gate_passed"])
        self.assertEqual(review["failed_cases"], ["environment_elyndor_road"])

    def test_missing_extra_and_reasonless_failures_fail_closed(self):
        judgments = self._judgments(CREATURE_CANARY_CASES, True)
        judgments.pop("enemy_creature_hexapod")
        with self.assertRaisesRegex(ValueError, "case mismatch"):
            record_creature_visual_review(workflow_run_id=1, head_sha="a"*40, artifact_digest="sha256:"+"b"*64, canary_version="v", judgments=judgments)
        judgments = self._judgments(CREATURE_CANARY_CASES, True)
        judgments["extra"] = {"passed": True, "reasons": []}
        with self.assertRaisesRegex(ValueError, "case mismatch"):
            record_creature_visual_review(workflow_run_id=1, head_sha="a"*40, artifact_digest="sha256:"+"b"*64, canary_version="v", judgments=judgments)
        judgments = self._judgments(CREATURE_CANARY_CASES, True)
        judgments["enemy_creature_hexapod"] = {"passed": False, "reasons": []}
        with self.assertRaisesRegex(ValueError, "requires at least one reason"):
            record_creature_visual_review(workflow_run_id=1, head_sha="a"*40, artifact_digest="sha256:"+"b"*64, canary_version="v", judgments=judgments)


if __name__ == "__main__": unittest.main()
