from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from modal_worker.world_tile_production_cli import RESULT_SCHEMA, run_production
from modal_worker.world_tile_package_exporter import validate_exported_package


def png_bytes(size: tuple[int, int] = (48, 48)) -> bytes:
    image = Image.new("RGBA", size, (1, 2, 3, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def manifest(source_path: str = "tile.png") -> dict[str, object]:
    slots: list[dict[str, object]] = []
    for index in range(128):
        row = index // 8
        col = index % 8
        base: dict[str, object] = {
            "slot_index": index,
            "row": row,
            "column": col,
            "x": col * 48,
            "y": row * 48,
        }
        if index == 0:
            base.update(
                {
                    "role": "a1_floor",
                    "asset_id": "test_tile",
                    "source_path": source_path,
                    "footprint_tiles": [1, 1],
                    "approval_status": "approved",
                    "approval_designation": "VERA_APPROVED_SOURCE_V1",
                    "production_authorized": True,
                    "provenance": "vera-chatgpt-approved",
                }
            )
        else:
            base.update({"role": "empty", "asset_id": None, "source_path": None})
        slots.append(base)
    return {
        "schema": "plushbound.world_tile_sheet.v1",
        "template_version": "WORLD_TILE_ASSET_V1",
        "sheet_id": "test-sheet",
        "material_id": "test-material",
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


class ProductionCliTests(unittest.TestCase):
    def test_end_to_end_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sources = root / "approved"
            outputs = root / "packages"
            sources.mkdir()
            (sources / "tile.png").write_bytes(png_bytes())
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")

            result = run_production(manifest_path, sources, outputs)
            self.assertEqual(result["schema"], RESULT_SCHEMA)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["production_authorized"])
            self.assertEqual(result["declared_source_count"], 1)
            self.assertFalse(result["runtime_import_proof"])
            package_dir = Path(str(result["package_dir"]))
            validation = validate_exported_package(package_dir)
            self.assertEqual(validation["status"], "READY_FOR_WORLD_EDITOR_HANDOFF")

    def test_source_escape_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sources = root / "approved"
            sources.mkdir()
            (root / "outside.png").write_bytes(png_bytes())
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest("../outside.png")), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "escapes approved source root"):
                run_production(manifest_path, sources, root / "packages")

    def test_missing_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sources = root / "approved"
            sources.mkdir()
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                run_production(manifest_path, sources, root / "packages")

    def test_existing_package_requires_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sources = root / "approved"
            outputs = root / "packages"
            sources.mkdir()
            (sources / "tile.png").write_bytes(png_bytes())
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
            run_production(manifest_path, sources, outputs)
            with self.assertRaises(FileExistsError):
                run_production(manifest_path, sources, outputs)
            result = run_production(manifest_path, sources, outputs, overwrite=True)
            self.assertEqual(result["status"], "PASS")

    def test_wrong_source_geometry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sources = root / "approved"
            sources.mkdir()
            (sources / "tile.png").write_bytes(png_bytes((96, 96)))
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest()), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires exact source size 48x48"):
                run_production(manifest_path, sources, root / "packages")


if __name__ == "__main__":
    unittest.main()
