import unittest
from pathlib import Path
class MiniJarvisWorkerSurfaceTests(unittest.TestCase):
 def test_worker_exposes_brain_and_planner_cpu_endpoints(self):
  source=Path(__file__).with_name("freeframe_worker.py").read_text(encoding="utf-8"); self.assertIn("def get_plushbound_brain()",source); self.assertIn("def plan_asset_job(request:dict)",source); self.assertIn("from modal_worker.plushbound_brain import brain_snapshot",source); self.assertIn("from modal_worker.mini_jarvis_controller import plan_asset",source)
 def test_planner_endpoint_does_not_call_gpu_generator(self):
  source=Path(__file__).with_name("freeframe_worker.py").read_text(encoding="utf-8"); start=source.index("def plan_asset_job(request:dict)"); end=source.index("@app.function",start); block=source[start:end]; self.assertNotIn("FreeFrameGenerator",block); self.assertNotIn(".remote(",block)
if __name__=="__main__": unittest.main()
