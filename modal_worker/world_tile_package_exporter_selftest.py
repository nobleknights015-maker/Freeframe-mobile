"""Regression tests for deterministic WORLD_TILE_ASSET_V1 export packages."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from modal_worker.a5_tilesheet_compiler import compile_world_tile_sheet
from modal_worker.a5_tilesheet_compiler_selftest import valid_manifest, WorldTileCompilerTests
from modal_worker.world_tile_package_exporter import (
    HANDOFF_REPORT_NAME,
    MANIFEST_NAME,
    METADATA_NAME,
    PACKAGE_INDEX_NAME,
    PNG_NAME,
    REQUIRED_FILES,
    export_world_tile_package,
    validate_exported_package,
)


class WorldTilePackageExporterTests(unittest.TestCase):
    def compiled(self) -> dict[str, object]:
        return compile_world_tile_sheet(valid_manifest(), WorldTileCompilerTests().sources())

    def test_export_writes_exact_canonical_package(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            package = export_world_tile_package(self.compiled(), Path(td))
            self.assertEqual(package.name, "tideglass_test__tideglass.test.sheet")
            self.assertEqual({p.name for p in package.iterdir()}, set(REQUIRED_FILES))
            result = validate_exported_package(package)
            self.assertEqual(result["status"], "READY_FOR_WORLD_EDITOR_HANDOFF")
            self.assertFalse(result["runtime_import_proof"])

    def test_export_is_fail_closed_when_compiler_metadata_is_tampered(self) -> None:
        compiled = self.compiled()
        metadata = copy.deepcopy(compiled["metadata"])
        metadata["png_sha256"] = "0" * 64
        compiled["metadata"] = metadata
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "PNG hash"):
                export_world_tile_package(compiled, Path(td))

    def test_existing_package_is_not_overwritten_without_explicit_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            export_world_tile_package(self.compiled(), root)
            with self.assertRaises(FileExistsError):
                export_world_tile_package(self.compiled(), root)

    def test_overwrite_replaces_only_after_new_package_validates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            package = export_world_tile_package(self.compiled(), root)
            marker = package / "forbidden-extra.txt"
            marker.write_text("old", encoding="utf-8")
            package2 = export_world_tile_package(self.compiled(), root, overwrite=True)
            self.assertEqual(package, package2)
            self.assertFalse(marker.exists())
            self.assertEqual({p.name for p in package2.iterdir()}, set(REQUIRED_FILES))

    def test_extra_file_breaks_package_validation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            package = export_world_tile_package(self.compiled(), Path(td))
            (package / "extra.txt").write_text("no", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly"):
                validate_exported_package(package)

    def test_embedded_handoff_report_must_match_recomputed_result(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            package = export_world_tile_package(self.compiled(), Path(td))
            report = package / HANDOFF_REPORT_NAME
            report.write_text('{"status":"FAKE"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "handoff report"):
                validate_exported_package(package)

    def test_package_index_must_match_contents(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            package = export_world_tile_package(self.compiled(), Path(td))
            index = package / PACKAGE_INDEX_NAME
            index.write_text('{"schema":"wrong"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "package index"):
                validate_exported_package(package)

    def test_canonical_file_names_are_locked(self) -> None:
        self.assertEqual(PNG_NAME, "runtime.png")
        self.assertEqual(MANIFEST_NAME, "manifest.json")
        self.assertEqual(METADATA_NAME, "compiler-metadata.json")
        self.assertEqual(HANDOFF_REPORT_NAME, "world-editor-handoff.json")
        self.assertEqual(PACKAGE_INDEX_NAME, "package.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
