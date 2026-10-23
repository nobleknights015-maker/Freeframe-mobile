import unittest

from extraction_routing import requires_subject_extraction
from extraction_smoke_plan import (
    EXTRACTION_SMOKE_VERSION,
    SMOKE_ASSET_IDS,
    extraction_smoke_requests,
)


class ExtractionSmokePlanTests(unittest.TestCase):
    def test_plan_is_exactly_two_v32_subject_assets(self):
        plan = extraction_smoke_requests()
        self.assertEqual(EXTRACTION_SMOKE_VERSION, "plushbound-extraction-smoke-v1")
        self.assertEqual(tuple(item["asset_id"] for item in plan), SMOKE_ASSET_IDS)
        self.assertEqual(len(plan), 2)
        for item in plan:
            self.assertTrue(requires_subject_extraction(item["asset_id"]))
            self.assertEqual(item["request"]["style_version"], "v3.2")
            self.assertEqual(item["request"]["seed"], item["seed"])

    def test_environment_is_never_in_smoke_plan(self):
        self.assertNotIn("environment_master", SMOKE_ASSET_IDS)
        self.assertFalse(requires_subject_extraction("environment_master"))


if __name__ == "__main__":
    unittest.main()
