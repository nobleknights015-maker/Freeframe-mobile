import unittest

from atlas_batch_bridge import BRIDGE_VERSION, batch_progress, build_batch_item, reconcile_batch_item
from atlas_controller import plan_asset
from batch_state import BatchState, stable_asset_id


class AtlasBatchBridgeTests(unittest.TestCase):
    def _item(self):
        plan = plan_asset({
            "family": "guardian_friendly",
            "description": "small meadow guardian with leaflike ears",
            "context": {"region": "Elyndor"},
            "seed": 7,
        })
        return build_batch_item(plan, path="Guardians/Elyndor/leaflet.png", profile="guardian_master")

    def test_build_batch_item_preserves_atlas_identity(self):
        item = self._item()
        self.assertEqual(item["atlas_bridge_version"], BRIDGE_VERSION)
        self.assertEqual(len(item["atlas_job_id"]), 24)
        self.assertEqual(len(item["plan_digest"]), 64)
        self.assertEqual(item["atlas_ledger_record"]["state"], "planned")

    def test_completed_batch_item_reconciles_to_accepted(self):
        item = self._item()
        state = BatchState(batch_id="b1", total=1)
        asset_id = stable_asset_id(item["path"], item["prompt"], item["profile"])
        state.mark_completed(asset_id, {"sha256": "abc", "retry_attempt": 1})
        record = reconcile_batch_item(item, state)
        self.assertEqual(record.state, "accepted")
        self.assertEqual(record.attempts, 1)

    def test_failed_batch_item_tracks_generation_failure_and_retries(self):
        item = self._item()
        state = BatchState(batch_id="b2", total=1)
        asset_id = stable_asset_id(item["path"], item["prompt"], item["profile"])
        state.mark_failed(asset_id, "RuntimeError: CUDA failure", 2)
        record = reconcile_batch_item(item, state)
        self.assertEqual(record.state, "generation_failed")
        self.assertEqual(record.attempts, 2)
        self.assertEqual([entry["event"] for entry in record.history].count("queue_retry"), 1)

    def test_pending_batch_item_stays_ready(self):
        item = self._item()
        state = BatchState(batch_id="b3", total=1)
        record = reconcile_batch_item(item, state)
        self.assertEqual(record.state, "ready")
        self.assertEqual(record.attempts, 0)

    def test_batch_progress_is_fail_closed(self):
        item = self._item()
        state = BatchState(batch_id="b4", total=1)
        progress = batch_progress([item], state)
        self.assertEqual(progress["ready_or_pending"], 1)
        self.assertEqual(progress["accepted"], 0)
        self.assertFalse(progress["automatic_full_production_authorized"])


if __name__ == "__main__":
    unittest.main()
