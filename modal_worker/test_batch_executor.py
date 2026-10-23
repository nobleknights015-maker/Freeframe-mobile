import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from batch_executor import deterministic_retry_variant, run_batch


class BatchExecutorTests(unittest.TestCase):
    def _items(self, count=25):
        return [
            {"path": f"img/{i}.png", "prompt": f"asset {i}", "profile": "character", "seed": 1000 + i}
            for i in range(count)
        ]

    def test_processes_batch_once(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(self._items(25), Path(tmp) / "state.json", "b1", lambda item: calls.append(item["path"]) or {"ok": True})
        self.assertEqual(state.done, 25)
        self.assertEqual(len(calls), 25)

    def test_resume_skips_completed_assets(self):
        items = self._items(10); calls = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            run_batch(items, path, "b1", lambda item: calls.append(item["path"]) or {"ok": True})
            run_batch(items, path, "b1", lambda item: calls.append("DUPLICATE") or {"ok": True})
        self.assertNotIn("DUPLICATE", calls); self.assertEqual(len(calls), 10)

    def test_transient_failure_retries_with_new_deterministic_seed(self):
        items = self._items(1); seen = []
        def flaky(item):
            seen.append((item["retry_attempt"], item["seed"]))
            if len(seen) < 3: raise RuntimeError("temporary")
            return {"ok": True}
        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(items, Path(tmp) / "state.json", "b1", flaky, max_attempts=3)
        self.assertEqual(seen, [(1, 1000), (2, 105729), (3, 210458)])
        self.assertEqual(state.done, 1)
        completed = next(iter(state.completed.values()))
        self.assertEqual(completed["retry_attempt"], 3)
        self.assertEqual(completed["effective_seed"], 210458)

    def test_inspection_rejection_uses_same_retry_path(self):
        items = self._items(1); seen = []
        def generate(item):
            seen.append(item["seed"]); return {"ok": True}
        def inspect(item, _metadata):
            return {"accepted": item["retry_attempt"] >= 2, "errors": ["semantic reject"]}
        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(items, Path(tmp) / "state.json", "b1", generate, inspect=inspect, max_attempts=3)
        self.assertEqual(seen, [1000, 105729])
        self.assertEqual(state.done, 1)

    def test_retry_transform_does_not_mutate_manifest_item(self):
        item = self._items(1)[0]; original = dict(item)
        variant = deterministic_retry_variant(item, 2)
        self.assertEqual(item, original)
        self.assertNotEqual(variant["seed"], item["seed"])

    def test_permanent_failure_stops_at_budget_and_resume_does_not_repeat(self):
        items = self._items(1); attempts = {"n": 0}
        def broken(_):
            attempts["n"] += 1; raise RuntimeError("broken")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"; state = run_batch(items, path, "b1", broken, max_attempts=3)
            self.assertEqual(attempts["n"], 3); self.assertEqual(len(state.failed), 1)
            run_batch(items, path, "b1", broken, max_attempts=3)
        self.assertEqual(attempts["n"], 3)

    def test_checkpoint_rejects_wrong_batch(self):
        items = self._items(1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"; run_batch(items, path, "b1", lambda _: {"ok": True})
            with self.assertRaises(ValueError): run_batch(items, path, "b2", lambda _: {"ok": True})

    def test_invalid_attempt_budget_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): run_batch(self._items(1), Path(tmp) / "state.json", "b1", lambda _: {}, max_attempts=0)

    def test_22k_manifest_dry_run(self):
        items = self._items(22000)
        with tempfile.TemporaryDirectory() as tmp, patch("batch_executor.save_atomic"):
            state = run_batch(items, Path(tmp) / "state.json", "large", lambda _: {"ok": True})
        self.assertEqual(state.done, 22000); self.assertEqual(state.pending, 0)


if __name__ == "__main__":
    unittest.main()
