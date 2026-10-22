import tempfile
import unittest
from pathlib import Path

from batch_executor import run_batch
from batch_state import stable_asset_id


ITEM = {"path": "img/characters/$hero.png", "prompt": "hero", "profile": "mv_single_character"}


class BatchProductionGateTests(unittest.TestCase):
    def test_rejected_inspection_never_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(
                [ITEM], Path(tmp) / "state.json", "gate-reject",
                lambda item: {"seed": 1},
                inspect=lambda item, meta: {"accepted": False, "errors": ["duplicate subject"]},
                max_attempts=1,
            )
            asset_id = stable_asset_id(ITEM["path"], ITEM["prompt"], ITEM["profile"])
            self.assertNotIn(asset_id, state.completed)
            self.assertEqual(state.failed[asset_id]["attempts"], 1)
            self.assertIn("duplicate subject", state.failed[asset_id]["error"])

    def test_accepted_inspection_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(
                [ITEM], Path(tmp) / "state.json", "gate-accept",
                lambda item: {"seed": 2},
                inspect=lambda item, meta: {"accepted": True, "errors": [], "warnings": []},
            )
            asset_id = stable_asset_id(ITEM["path"], ITEM["prompt"], ITEM["profile"])
            meta = state.completed[asset_id]
            self.assertEqual(meta["seed"], 2)
            self.assertTrue(meta["production_inspection"]["accepted"])

    def test_retry_can_recover_after_inspection_rejection(self):
        calls = {"count": 0}
        def inspect(item, meta):
            calls["count"] += 1
            if calls["count"] == 1:
                return {"accepted": False, "errors": ["border detected"]}
            return {"accepted": True, "errors": []}

        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(
                [ITEM], Path(tmp) / "state.json", "gate-retry",
                lambda item: {"seed": calls["count"] + 10},
                inspect=inspect,
                max_attempts=2,
            )
            asset_id = stable_asset_id(ITEM["path"], ITEM["prompt"], ITEM["profile"])
            self.assertIn(asset_id, state.completed)
            self.assertNotIn(asset_id, state.failed)
            self.assertEqual(calls["count"], 2)

    def test_resume_skips_completed_asset(self):
        calls = {"generate": 0}
        def generate(item):
            calls["generate"] += 1
            return {"seed": 99}

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            run_batch([ITEM], path, "gate-resume", generate, inspect=lambda i, m: {"accepted": True, "errors": []})
            run_batch([ITEM], path, "gate-resume", generate, inspect=lambda i, m: {"accepted": True, "errors": []})
            self.assertEqual(calls["generate"], 1)


if __name__ == "__main__":
    unittest.main()
