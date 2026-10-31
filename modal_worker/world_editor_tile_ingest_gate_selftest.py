"""Regression tests for the fail-closed World Editor tile handoff boundary."""
from __future__ import annotations

import copy
import unittest

from modal_worker.a5_tilesheet_compiler import compile_world_tile_sheet
from modal_worker.a5_tilesheet_compiler_selftest import valid_manifest, WorldTileCompilerTests
from modal_worker.world_editor_tile_ingest_gate import validate_world_editor_handoff


class WorldEditorTileIngestGateTests(unittest.TestCase):
    def package(self):
        manifest = valid_manifest()
        compiled = compile_world_tile_sheet(manifest, WorldTileCompilerTests().sources())
        return compiled["png"], manifest, compiled["metadata"]

    def test_valid_compiled_package_is_accepted_for_handoff(self) -> None:
        png, manifest, metadata = self.package()
        report = validate_world_editor_handoff(png, manifest, metadata)
        self.assertEqual(report["status"], "ACCEPTED_FOR_WORLD_EDITOR_HANDOFF")
        self.assertTrue(report["world_editor_must_consume_manifest"])
        self.assertFalse(report["visual_layout_inference_allowed"])
        self.assertFalse(report["automatic_repair_allowed"])
        self.assertFalse(report["runtime_import_proof"])
        self.assertEqual(report["slot_count"], 128)

    def test_png_hash_mismatch_is_rejected(self) -> None:
        png, manifest, metadata = self.package()
        bad = bytearray(png)
        bad[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "PNG hash"):
            validate_world_editor_handoff(bytes(bad), manifest, metadata)

    def test_manifest_hash_mismatch_is_rejected(self) -> None:
        png, manifest, metadata = self.package()
        bad_manifest = copy.deepcopy(manifest)
        bad_manifest["sheet_id"] = "changed.after.compile"
        with self.assertRaisesRegex(ValueError, "manifest hash"):
            validate_world_editor_handoff(png, bad_manifest, metadata)

    def test_unknown_compiler_is_rejected(self) -> None:
        png, manifest, metadata = self.package()
        bad = dict(metadata)
        bad["compiler_version"] = "mystery-compiler"
        with self.assertRaisesRegex(ValueError, "unauthorized compiler_version"):
            validate_world_editor_handoff(png, manifest, bad)

    def test_resize_claim_is_rejected(self) -> None:
        png, manifest, metadata = self.package()
        bad = dict(metadata)
        bad["resized_after_generation"] = True
        with self.assertRaisesRegex(ValueError, "resized_after_generation"):
            validate_world_editor_handoff(png, manifest, bad)

    def test_visual_inference_claim_is_rejected(self) -> None:
        png, manifest, metadata = self.package()
        bad = dict(metadata)
        bad["layout_inferred_visually"] = True
        with self.assertRaisesRegex(ValueError, "layout_inferred_visually"):
            validate_world_editor_handoff(png, manifest, bad)

    def test_reference_pixel_claim_is_rejected(self) -> None:
        png, manifest, metadata = self.package()
        bad = dict(metadata)
        bad["reference_sheet_pixels_used_as_runtime_art"] = True
        with self.assertRaisesRegex(ValueError, "reference_sheet_pixels"):
            validate_world_editor_handoff(png, manifest, bad)

    def test_coordinate_drift_is_rejected_even_if_png_is_unchanged(self) -> None:
        png, manifest, metadata = self.package()
        bad_manifest = copy.deepcopy(manifest)
        bad_manifest["slots"][10]["x"] += 48
        with self.assertRaisesRegex(ValueError, "x must be exactly"):
            validate_world_editor_handoff(png, bad_manifest, metadata)

    def test_bad_coverage_is_rejected(self) -> None:
        png, manifest, metadata = self.package()
        bad_manifest = copy.deepcopy(manifest)
        bad_manifest["slots"][105]["covered_by"] = "wrong.owner"
        with self.assertRaisesRegex(ValueError, "covered_by"):
            validate_world_editor_handoff(png, bad_manifest, metadata)

    def test_source_hash_ledger_must_match_anchor_ids(self) -> None:
        png, manifest, metadata = self.package()
        bad = copy.deepcopy(metadata)
        bad["source_png_sha256"].pop("tideglass.floor.base")
        with self.assertRaisesRegex(ValueError, "source hash ledger"):
            validate_world_editor_handoff(png, manifest, bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
