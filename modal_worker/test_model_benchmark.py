import unittest

from benchmark_report import BenchmarkResult, summarize
from model_catalog import apply_model_defaults, get_candidate, get_production_renderer


class ModelCatalogTests(unittest.TestCase):
    def test_smoke_model_is_not_production_eligible(self):
        self.assertFalse(get_candidate("sd_turbo_smoke").production_eligible)

    def test_flux_candidate_uses_distilled_defaults(self):
        candidate = get_candidate("flux_schnell_candidate")
        request = apply_model_defaults({"prompt": "guardian", "steps": 30, "guidance_scale": 6.0}, candidate)
        self.assertEqual(request["steps"], 4)
        self.assertEqual(request["guidance_scale"], 0.0)
        self.assertEqual(request["model_candidate"], candidate.key)

    def test_flux2_klein_4b_is_bounded_production_renderer_with_distilled_defaults(self):
        candidate = get_candidate("flux2_klein_4b_candidate")
        self.assertEqual(candidate.model_id, "black-forest-labs/FLUX.2-klein-4B")
        self.assertTrue(candidate.production_eligible)
        self.assertEqual(get_production_renderer(), candidate)
        request = apply_model_defaults({"prompt": "guardian", "steps": 28, "guidance_scale": 6.0}, candidate)
        self.assertEqual(request["steps"], 4)
        self.assertEqual(request["guidance_scale"], 1.0)
        self.assertEqual(request["model_candidate"], candidate.key)
        self.assertEqual(request["model_id"], candidate.model_id)

    def test_flux2_klein_fp8_stays_experimental(self):
        candidate = get_candidate("flux2_klein_4b_fp8_candidate")
        self.assertEqual(candidate.dtype, "float8_e4m3fn")
        self.assertFalse(candidate.production_eligible)
        self.assertEqual(candidate.default_steps, 4)
        self.assertEqual(candidate.default_guidance, 1.0)

    def test_unknown_candidate_rejected(self):
        with self.assertRaises(ValueError):
            get_candidate("nope")


class BenchmarkReportTests(unittest.TestCase):
    def test_summary_projects_gpu_hours(self):
        results = [
            BenchmarkResult("a", 2.0, True, 512, 512, 100, "a" * 64, "model", 1, 8.0),
            BenchmarkResult("b", 4.0, True, 512, 512, 100, "b" * 64, "model", 2, 6.0),
        ]
        summary = summarize(results, projected_assets=22_000)
        self.assertEqual(summary["average_inference_seconds"], 3.0)
        self.assertEqual(summary["projected_raw_gpu_hours"], 18.33)
        self.assertEqual(summary["average_visual_score"], 7.0)
        self.assertEqual(summary["invalid_cases"], [])

    def test_empty_results_rejected(self):
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == "__main__":
    unittest.main()
