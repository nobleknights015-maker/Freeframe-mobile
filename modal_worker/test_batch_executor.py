import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from batch_executor import run_batch


class BatchExecutorTests(unittest.TestCase):
    def _items(self, count=25):
        return [
            {"path": f"img/{i}.png", "prompt": f"asset {i}", "profile": "character"}
            for i in range(count)
        ]

    def test_processes_batch_once(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(
                self._items(25), Path(tmp) / "state.json", "b1",
                lambda item: calls.append(item["path"]) or {"ok": True},
            )
        self.assertEqual(state.done, 25)
        self.assertEqual(len(calls), 25)

    def test_resume_skips_completed_assets(self):
        items = self._items(10)
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            run_batch(items, path, "b1", lambda item: calls.append(item["path"]) or {"ok": True})
            run_batch(items, path, "b1", lambda item: calls.append("DUPLICATE") or {"ok": True})
        self.assertNotIn("DUPLICATE", calls)
        self.assertEqual(len(calls), 10)

    def test_transient_failure_retries_then_succeeds(self):
        items = self._items(1)
        attempts = {"n": 0}
        def flaky(_):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise RuntimeError("temporary")
            return {"ok": True}
        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(items, Path(tmp) / "state.json", "b1", flaky, max_attempts=3)
        self.assertEqual(attempts["n"], 3)
        self.assertEqual(state.done, 1)
        self.assertEqual(state.failed, {})

    def test_permanent_failure_stops_at_budget_and_resume_does_not_repeat(self):
        items = self._items(1)
        attempts = {"n": 0}
        def broken(_):
            attempts["n"] += 1
            raise RuntimeError("broken")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = run_batch(items, path, "b1", broken, max_attempts=3)
            self.assertEqual(attempts["n"], 3)
            self.assertEqual(len(state.failed), 1)
            run_batch(items, path, "b1", broken, max_attempts=3)
        self.assertEqual(attempts["n"], 3)

    def test_checkpoint_rejects_wrong_batch(self):
        items = self._items(1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            run_batch(items, path, "b1", lambda _: {"ok": True})
            with self.assertRaises(ValueError):
                run_batch(items, path, "b2", lambda _: {"ok": True})

    def test_22k_manifest_dry_run(self):
        # Per-item atomic fsync behavior is tested separately in test_batch_state.
        # Here we stress the 22k-item orchestration path without doing 22k disk syncs.
        items = self._items(22000)
        with tempfile.TemporaryDirectory() as tmp, patch("batch_executor.save_atomic"):
            state = run_batch(items, Path(tmp) / "state.json", "large", lambda _: {"ok": True})
        self.assertEqual(state.done, 22000)
        self.assertEqual(state.pending, 0)


if __name__ == "__main__":
    unittest.main()
