import json
import tempfile
import unittest
from pathlib import Path

from batch_state import BatchState, load, save_atomic, stable_asset_id


class BatchStateTests(unittest.TestCase):
    def test_asset_ids_are_deterministic(self):
        a = stable_asset_id("img/actor.png", "hero", "character")
        b = stable_asset_id("img/actor.png", "hero", "character")
        c = stable_asset_id("img/actor.png", "villain", "character")
        self.assertEqual(a, b); self.assertNotEqual(a, c)

    def test_completed_wins_over_failure(self):
        state = BatchState("demo", 3); state.mark_failed("a", "timeout", 1); state.mark_completed("a", {"sha256": "abc"}); state.mark_failed("a", "late error", 2)
        self.assertIn("a", state.completed); self.assertNotIn("a", state.failed); self.assertEqual(state.done, 1); self.assertEqual(state.pending, 2)

    def test_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"; state = BatchState("demo", 22000); state.mark_completed("one", {"path": "one.png"}); save_atomic(path, state)
            restored = load(path); self.assertEqual(restored.batch_id, "demo"); self.assertEqual(restored.total, 22000); self.assertEqual(restored.completed["one"]["path"], "one.png")

    def test_corrupt_primary_recovers_from_previous_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            first = BatchState("demo", 3); first.mark_completed("a", {"path": "a.png"}); save_atomic(path, first)
            second = BatchState("demo", 3); second.mark_completed("a", {"path": "a.png"}); second.mark_completed("b", {"path": "b.png"}); save_atomic(path, second)
            path.write_text("{corrupt", encoding="utf-8")
            restored = load(path)
            self.assertIn("a", restored.completed); self.assertNotIn("b", restored.completed)

    def test_both_corrupt_raise_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"; path.write_text("bad", encoding="utf-8"); Path(str(path) + ".bak").write_text("also bad", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "primary and backup"):
                load(path)

    def test_invalid_state_invariants_rejected(self):
        with self.assertRaises(ValueError): BatchState.from_dict({"version": 1, "batch_id": "x", "total": -1})
        with self.assertRaises(ValueError): BatchState.from_dict({"version": 1, "batch_id": "x", "total": 1, "completed": {"a": {}}, "failed": {"a": {}}})
        with self.assertRaises(ValueError): BatchState.from_dict({"version": 1, "batch_id": "x", "total": 0, "completed": {"a": {}}})

    def test_unknown_manifest_version_rejected(self):
        with self.assertRaises(ValueError): BatchState.from_dict({"version": 99, "batch_id": "x", "total": 1})


if __name__ == "__main__":
    unittest.main()
