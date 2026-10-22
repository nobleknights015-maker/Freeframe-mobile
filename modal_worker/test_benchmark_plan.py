import unittest

from benchmark_plan import CASES, build_requests


class BenchmarkPlanTests(unittest.TestCase):
    def test_plan_covers_core_asset_categories(self):
        presets = {case.preset for case in CASES}
        self.assertEqual(
            presets,
            {
                "plushbound_guardian",
                "plushbound_character",
                "plushbound_enemy",
                "plushbound_environment",
            },
        )

    def test_case_ids_and_seeds_are_unique(self):
        self.assertEqual(len({case.case_id for case in CASES}), len(CASES))
        self.assertEqual(len({case.seed for case in CASES}), len(CASES))

    def test_requests_preserve_preset_identity(self):
        requests = build_requests()
        self.assertEqual(len(requests), len(CASES))
        for case, request in zip(CASES, requests):
            self.assertEqual(request["style_preset"], case.preset)
            self.assertEqual(request["seed"], case.seed)


if __name__ == "__main__":
    unittest.main()
