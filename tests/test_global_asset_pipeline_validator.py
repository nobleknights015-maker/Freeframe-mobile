from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from modal_worker.global_asset_pipeline_validator import validate_global_asset_pipeline

REGISTRY = Path("approved_art/PLUSHBOUND_GLOBAL_ASSET_PIPELINE_V1.json")


class GlobalAssetPipelineValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_locked_registry_is_valid(self):
        validate_global_asset_pipeline(self.base)

    def test_region_cannot_become_primary_partition(self):
        data = copy.deepcopy(self.base)
        data["primary_partition"] = "region"
        with self.assertRaisesRegex(ValueError, "asset_class"):
            validate_global_asset_pipeline(data)

    def test_missing_non_tile_class_fails(self):
        data = copy.deepcopy(self.base)
        data["asset_classes"] = [row for row in data["asset_classes"] if row["id"] != "faces_portraits"]
        with self.assertRaisesRegex(ValueError, "faces_portraits"):
            validate_global_asset_pipeline(data)

    def test_missing_audio_class_fails(self):
        data = copy.deepcopy(self.base)
        data["asset_classes"] = [row for row in data["asset_classes"] if row["id"] != "audio_se"]
        with self.assertRaisesRegex(ValueError, "audio_se"):
            validate_global_asset_pipeline(data)

    def test_reference_pixels_cannot_be_authorized(self):
        data = copy.deepcopy(self.base)
        data["external_reference_pixels_allowed_in_runtime"] = True
        with self.assertRaisesRegex(ValueError, "reference pixels"):
            validate_global_asset_pipeline(data)

    def test_showcase_generation_cannot_be_reenabled(self):
        data = copy.deepcopy(self.base)
        data["global_generation_rules"]["sheet_showcase_generation_allowed"] = True
        with self.assertRaisesRegex(ValueError, "sheet_showcase_generation_allowed"):
            validate_global_asset_pipeline(data)

    def test_all_asset_classes_have_owner_and_unit(self):
        for row in self.base["asset_classes"]:
            self.assertTrue(row["production_owner"])
            self.assertTrue(row["generation_unit"])


if __name__ == "__main__":
    unittest.main()
