import copy
import unittest

from atlas_production_ledger import AssetProductionRecord, LEDGER_VERSION, new_record, summarize, transition, verify_history


class AtlasProductionLedgerTests(unittest.TestCase):
    def test_happy_path_reaches_accepted_with_two_receipts(self):
        record = new_record("job-1", "guardian_friendly", "digest-1")
        transition(record, "plan_validated", {"validator": "contract"})
        transition(record, "generation_succeeded", {"sha256": "abc"})
        transition(record, "qa_passed", {"visual_qa": "pass"})
        self.assertEqual(record.state, "accepted")
        self.assertEqual(record.attempts, 1)
        self.assertEqual(len(record.history), 3)
        verify_history(record)

    def test_retry_path_counts_render_attempts_only(self):
        record = new_record("job-2", "enemy_creature", "digest-2")
        transition(record, "plan_validated")
        transition(record, "generation_succeeded", {"sha256": "first"})
        transition(record, "qa_failed", {"reason": "toy-like"})
        transition(record, "queue_retry", {"repair": "stronger organism anatomy"})
        transition(record, "generation_succeeded", {"sha256": "second"})
        transition(record, "qa_passed")
        self.assertEqual(record.state, "accepted")
        self.assertEqual(record.attempts, 2)

    def test_final_state_cannot_be_reopened(self):
        record = new_record("job-3", "guardian_boss", "digest-3")
        transition(record, "plan_validated")
        transition(record, "generation_succeeded")
        transition(record, "qa_passed")
        with self.assertRaisesRegex(ValueError, "final state"):
            transition(record, "quarantine")

    def test_tampering_breaks_receipt_chain(self):
        record = new_record("job-4", "guardian_corrupt", "digest-4")
        transition(record, "plan_validated")
        transition(record, "generation_succeeded", {"sha256": "good"})
        damaged = copy.deepcopy(record.to_dict())
        damaged["history"][1]["metadata"]["sha256"] = "tampered"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            AssetProductionRecord.from_dict(damaged)

    def test_summary_separates_complete_and_attention(self):
        accepted = new_record("a", "guardian_friendly", "d1")
        transition(accepted, "plan_validated")
        transition(accepted, "generation_succeeded")
        transition(accepted, "qa_passed")
        failed = new_record("b", "enemy_creature", "d2")
        transition(failed, "plan_validated")
        transition(failed, "generation_succeeded")
        transition(failed, "qa_failed", {"reason": "not textile enough"})
        result = summarize([accepted, failed])
        self.assertEqual(result["ledger_version"], LEDGER_VERSION)
        self.assertEqual(result["complete"], 1)
        self.assertEqual(result["needs_attention"], 1)
        self.assertEqual(result["attempts"], 2)
        self.assertFalse(result["automatic_full_production_authorized"])


if __name__ == "__main__":
    unittest.main()
