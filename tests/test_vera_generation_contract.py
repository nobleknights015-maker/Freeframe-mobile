from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from modal_worker.vera_generation_contract_validator import (
    validate_batch,
    validate_contract,
    validate_files,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "approved_art/generation_contracts/VERA_WORLD_TILE_GENERATION_V1.json"
BATCH = ROOT / "approved_art/generation_contracts/tideglass_world_tiles_v1.json"


class VeraGenerationContractTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.batch = json.loads(BATCH.read_text(encoding="utf-8"))

    def test_locked_files_validate(self):
        validate_files(CONTRACT, BATCH)

    def test_rejects_sheet_generation(self):
        bad = copy.deepcopy(self.contract)
        bad["sheet_generation_allowed"] = True
        with self.assertRaisesRegex(ValueError, "sheet_generation_allowed"):
            validate_contract(bad)

    def test_rejects_multiple_output_count(self):
        bad = copy.deepcopy(self.contract)
        bad["generation_output_contract"]["count"] = 4
        with self.assertRaisesRegex(ValueError, "exactly 1"):
            validate_contract(bad)

    def test_rejects_preapproved_generated_art(self):
        bad = copy.deepcopy(self.contract)
        bad["generation_output_contract"]["production_authorized_before_review"] = True
        with self.assertRaisesRegex(ValueError, "before review"):
            validate_contract(bad)

    def test_rejects_wrong_pixel_size_for_footprint(self):
        bad = copy.deepcopy(self.batch)
        bad["targets"][0]["pixel_size"] = [384, 768]
        with self.assertRaisesRegex(ValueError, "pixel_size"):
            validate_batch(bad)

    def test_rejects_duplicate_asset_id(self):
        bad = copy.deepcopy(self.batch)
        bad["targets"].append(copy.deepcopy(bad["targets"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate asset_id"):
            validate_batch(bad)

    def test_rejects_showcase_language(self):
        bad = copy.deepcopy(self.batch)
        bad["targets"][0]["required_elements"].append("assortment of mixed props")
        with self.assertRaisesRegex(ValueError, "assortment/showcase"):
            validate_batch(bad)

    def test_dock_timber_explicitly_bans_old_drift_elements(self):
        dock = next(t for t in self.batch["targets"] if t["asset_id"] == "tideglass.dock_timber")
        forbidden = {v.lower() for v in dock["forbidden_elements"]}
        for required in ("posts", "rope coils", "railings", "crates", "water", "dock silhouette"):
            self.assertIn(required, forbidden)


if __name__ == "__main__":
    unittest.main()
