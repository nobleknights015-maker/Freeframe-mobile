import unittest
from pathlib import Path


class AtlasWorkerSurfaceTests(unittest.TestCase):
    def test_worker_exposes_brain_planner_ledger_and_visual_gate_cpu_endpoints(self):
        source = Path(__file__).with_name("freeframe_worker.py").read_text(encoding="utf-8")
        self.assertIn("def get_plushbound_brain()", source)
        self.assertIn("def plan_asset_job(request:dict)", source)
        self.assertIn("def advance_atlas_record(request:dict)", source)
        self.assertIn("def summarize_atlas_records(request:dict)", source)
        self.assertIn("def record_atlas_visual_review(request:dict)", source)
        self.assertIn("from modal_worker.plushbound_brain import brain_snapshot", source)
        self.assertIn("from modal_worker.atlas_controller import plan_asset", source)
        self.assertIn("from modal_worker.atlas_production_ledger import AssetProductionRecord, transition", source)
        self.assertIn("from modal_worker.atlas_production_ledger import AssetProductionRecord, summarize", source)
        self.assertIn("from modal_worker.atlas_visual_gate import record_creature_visual_review", source)

    def test_atlas_cpu_endpoints_do_not_call_gpu_generator(self):
        source = Path(__file__).with_name("freeframe_worker.py").read_text(encoding="utf-8")
        starts = [
            source.index("def plan_asset_job(request:dict)"),
            source.index("def advance_atlas_record(request:dict)"),
            source.index("def summarize_atlas_records(request:dict)"),
            source.index("def record_atlas_visual_review(request:dict)"),
        ]
        for start in starts:
            end = source.index("@app.function", start)
            block = source[start:end]
            self.assertNotIn("FreeFrameGenerator", block)
            self.assertNotIn(".remote(", block)


if __name__ == "__main__":
    unittest.main()
