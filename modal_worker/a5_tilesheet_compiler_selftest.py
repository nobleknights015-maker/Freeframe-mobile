"""Fail-closed regression tests for WORLD_TILE_ASSET_V1 compilation."""
from __future__ import annotations

import copy
import hashlib
import io
import unittest

from PIL import Image

from modal_worker.a5_tilesheet_compiler import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    COLUMNS,
    ROWS,
    SLOT_COUNT,
    TILE_SIZE,
    compile_world_tile_sheet,
    validate_world_tile_manifest,
)


def make_png(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    image = Image.new("RGBA", (width, height), rgba)
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=False)
    return out.getvalue()


def role_for_slot(index: int) -> str:
    if index <= 31:
        return "a1_floor"
    if index <= 55:
        return "a2_wall"
    if index <= 79:
        return "a3_edge_corner"
    if index <= 103:
        return "a4_prop"
    return "a5_variation"


def empty_slot(index: int) -> dict:
    row = index // COLUMNS
    column = index % COLUMNS
    return {
        "slot_index": index,
        "row": row,
        "column": column,
        "x": column * TILE_SIZE,
        "y": row * TILE_SIZE,
        "role": "empty",
        "asset_id": None,
        "source_path": None,
    }


def approved_anchor(index: int, asset_id: str, source_path: str, footprint: list[int]) -> dict:
    row = index // COLUMNS
    column = index % COLUMNS
    return {
        "slot_index": index,
        "row": row,
        "column": column,
        "x": column * TILE_SIZE,
        "y": row * TILE_SIZE,
        "role": role_for_slot(index),
        "asset_id": asset_id,
        "source_path": source_path,
        "footprint_tiles": footprint,
        "approval_status": "approved",
        "approval_designation": "VERA_APPROVED_SOURCE_V1",
        "provenance": "vera-chatgpt-approved",
        "production_authorized": True,
    }


def covered_slot(index: int, owner: str) -> dict:
    row = index // COLUMNS
    column = index % COLUMNS
    return {
        "slot_index": index,
        "row": row,
        "column": column,
        "x": column * TILE_SIZE,
        "y": row * TILE_SIZE,
        "role": role_for_slot(index),
        "asset_id": None,
        "source_path": None,
        "covered_by": owner,
    }


def valid_manifest() -> dict:
    slots = [empty_slot(i) for i in range(SLOT_COUNT)]
    slots[0] = approved_anchor(0, "tideglass.floor.base", "sources/floor.png", [1, 1])

    owner = "tideglass.detail.large"
    slots[104] = approved_anchor(104, owner, "sources/detail_large.png", [2, 2])
    for index in (105, 112, 113):
        slots[index] = covered_slot(index, owner)

    return {
        "schema": "plushbound.world_tile_sheet.v1",
        "template_version": "WORLD_TILE_ASSET_V1",
        "sheet_id": "tideglass.test.sheet",
        "material_id": "tideglass_test",
        "canvas_width": 384,
        "canvas_height": 768,
        "tile_size": 48,
        "columns": 8,
        "rows": 16,
        "provenance": "vera-chatgpt-approved",
        "generator_calls_allowed": False,
        "gpu_allowed": False,
        "slots": slots,
    }


class WorldTileCompilerTests(unittest.TestCase):
    def sources(self) -> dict[str, bytes]:
        return {
            "tideglass.floor.base": make_png(48, 48, (10, 20, 30, 255)),
            "tideglass.detail.large": make_png(96, 96, (120, 130, 140, 255)),
        }

    def test_valid_manifest_compiles_exact_geometry_and_hashes(self) -> None:
        manifest = valid_manifest()
        result = compile_world_tile_sheet(manifest, self.sources())
        raw = result["png"]
        meta = result["metadata"]

        self.assertEqual((meta["width"], meta["height"]), (CANVAS_WIDTH, CANVAS_HEIGHT))
        self.assertEqual((CANVAS_WIDTH, CANVAS_HEIGHT), (384, 768))
        self.assertEqual((meta["columns"], meta["rows"]), (COLUMNS, ROWS))
        self.assertEqual(meta["slot_count"], SLOT_COUNT)
        self.assertFalse(meta["resized_after_generation"])
        self.assertFalse(meta["layout_inferred_visually"])
        self.assertFalse(meta["reference_sheet_pixels_used_as_runtime_art"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["png_sha256"])
        self.assertEqual(
            hashlib.sha256(self.sources()["tideglass.detail.large"]).hexdigest(),
            meta["source_png_sha256"]["tideglass.detail.large"],
        )

        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            self.assertEqual(image.size, (384, 768))
            self.assertEqual(image.getpixel((0, 0)), (10, 20, 30, 255))
            # 2x2 anchor at slot 104 => row 13, column 0; verify opposite corner.
            self.assertEqual(image.getpixel((95, 13 * 48 + 95)), (120, 130, 140, 255))

    def test_coordinate_drift_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["slots"][4]["x"] = 999
        with self.assertRaisesRegex(ValueError, "x must be exactly"):
            validate_world_tile_manifest(manifest)

    def test_role_band_mismatch_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["slots"][0]["role"] = "a5_variation"
        with self.assertRaisesRegex(ValueError, "role must be"):
            validate_world_tile_manifest(manifest)

    def test_missing_2x2_coverage_declaration_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["slots"][105] = empty_slot(105)
        with self.assertRaisesRegex(ValueError, "must declare covered_by"):
            validate_world_tile_manifest(manifest)

    def test_2x2_role_band_crossing_is_rejected(self) -> None:
        manifest = valid_manifest()
        # Slot 31 is the last A1 slot; a 2x2 footprint would enter A2.
        manifest["slots"][31] = approved_anchor(31, "bad.cross", "sources/cross.png", [2, 2])
        with self.assertRaisesRegex(ValueError, "role-band boundary|locked 8x16 grid"):
            validate_world_tile_manifest(manifest)

    def test_unapproved_source_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["slots"][0]["approval_status"] = "reference_only"
        with self.assertRaisesRegex(ValueError, "approval_status"):
            validate_world_tile_manifest(manifest)

    def test_target_size_resize_directive_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["slots"][0]["target_size"] = 48
        with self.assertRaisesRegex(ValueError, "target_size is forbidden"):
            validate_world_tile_manifest(manifest)

    def test_wrong_source_dimensions_are_rejected_not_resized(self) -> None:
        sources = self.sources()
        sources["tideglass.floor.base"] = make_png(47, 48, (1, 2, 3, 255))
        with self.assertRaisesRegex(ValueError, "requires exact source size 48x48"):
            compile_world_tile_sheet(valid_manifest(), sources)

    def test_undeclared_source_is_rejected(self) -> None:
        sources = self.sources()
        sources["surprise.asset"] = make_png(48, 48, (1, 2, 3, 255))
        with self.assertRaisesRegex(ValueError, "undeclared source assets"):
            compile_world_tile_sheet(valid_manifest(), sources)

    def test_duplicate_asset_ids_are_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["slots"][1] = approved_anchor(
            1, "tideglass.floor.base", "sources/duplicate.png", [1, 1]
        )
        with self.assertRaisesRegex(ValueError, "duplicate non-empty asset_id"):
            validate_world_tile_manifest(manifest)

    def test_empty_slots_remain_explicit_and_stable(self) -> None:
        manifest = valid_manifest()
        validate_world_tile_manifest(manifest)
        self.assertEqual(len(manifest["slots"]), 128)
        self.assertEqual([row["slot_index"] for row in manifest["slots"]], list(range(128)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
