import unittest
from types import SimpleNamespace

from production_run_report import build_run_report, should_pause_batch


class ProductionRunReportTests(unittest.TestCase):
    def test_reports_first_pass_retry_and_failure_health(self):
        state = SimpleNamespace(
            batch_id="plushtopia-1", total=5,
            completed={
                "a": {"retry_attempt": 1},
                "b": {"retry_attempt": 1},
                "c": {"retry_attempt": 2},
            },
            failed={"d": {"attempts": 3}},
        )
        r = build_run_report(state)
        self.assertEqual(r["completed"], 3)
        self.assertEqual(r["first_pass"], 2)
        self.assertEqual(r["recovered_by_retry"], 1)
        self.assertEqual(r["unresolved"], 1)
        self.assertEqual(r["pending"], 1)
        self.assertEqual(r["failed_attempts"], 3)
        self.assertFalse(r["healthy"])

    def test_circuit_breaker_ignores_small_quarantine_rate(self):
        self.assertFalse(should_pause_batch({"total": 22000, "unresolved": 100}))
        self.assertTrue(should_pause_batch({"total": 22000, "unresolved": 1200}))

    def test_empty_batch_is_safe(self):
        r = build_run_report(SimpleNamespace(batch_id="empty", total=0, completed={}, failed={}))
        self.assertEqual(r["completion_rate"], 1.0)
        self.assertFalse(should_pause_batch(r))


if __name__ == "__main__":
    unittest.main()
