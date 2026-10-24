import unittest
from pathlib import Path


class WorkerProductionRoutingTests(unittest.TestCase):
    def test_worker_has_dedicated_klein_production_renderer(self):
        source = Path(__file__).with_name("freeframe_worker.py").read_text(encoding="utf-8")
        self.assertIn('PRODUCTION_MODEL = "black-forest-labs/FLUX.2-klein-4B"', source)
        self.assertIn('PRODUCTION_RENDERER_ROUTE = "flux2_klein"', source)
        self.assertIn("class FreeFrameProductionGenerator", source)
        self.assertIn("DiffusionPipeline.from_pretrained(PRODUCTION_MODEL", source)
        self.assertIn("torch_dtype=torch.bfloat16", source)
        self.assertIn('if route == PRODUCTION_RENDERER_ROUTE:', source)
        self.assertIn("FreeFrameProductionGenerator().generate.remote(request)", source)

    def test_production_renderer_fails_closed_on_route_and_model_mismatch(self):
        source = Path(__file__).with_name("freeframe_worker.py").read_text(encoding="utf-8")
        self.assertIn('raise ValueError("production generator requires flux2_klein renderer_route")', source)
        self.assertIn('raise ValueError("production request model_id does not match deployed production renderer")', source)
        self.assertIn('raise ValueError(f"unknown FreeFrame renderer_route: {route}")', source)

    def test_full_catalog_launch_stays_locked(self):
        source = Path(__file__).with_name("freeframe_worker.py").read_text(encoding="utf-8")
        self.assertIn('"automatic_full_production_authorized":False', source)


if __name__ == "__main__":
    unittest.main()
