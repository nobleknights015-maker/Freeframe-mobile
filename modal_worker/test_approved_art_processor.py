from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from approved_art_processor import _safe_child, _validate_manifest, process_manifest


class ApprovedArtProcessorTests(unittest.TestCase):
    def _asset(self, **overrides):
        asset = {
            "asset_id": "tideglass.test_asset",
            "source_path": "sources/test.png",
            "footprint_tiles": [1, 1],
            "output_name": "tideglass/test.png",
            "approval_status": "approved",
            "approval_designation": "VERA_APPROVED_SOURCE_V1",
            "production_authorized": True,
            "provenance": "vera-chatgpt-approved",
        }
        asset.update(overrides)
        return asset

    def _manifest(self, assets=None):
        return {
            "schema": "plushbound.approved_art_round.v1",
            "round_id": "test-round",
            "provenance": "vera-chatgpt-approved",
            "generator_calls_allowed": False,
            "gpu_allowed": False,
            "assets": assets or [self._asset()],
        }

    def test_rejects_target_size_resizing(self):
        data = self._manifest([self._asset(target_size=48)])
        with self.assertRaisesRegex(ValueError, "target_size is forbidden"):
            _validate_manifest(data)

    def test_rejects_missing_visual_approval(self):
        data = self._manifest([self._asset(approval_status="pending")])
        with self.assertRaisesRegex(ValueError, "approval_status"):
            _validate_manifest(data)

    def test_rejects_duplicate_asset_ids(self):
        data = self._manifest([self._asset(), self._asset(output_name="other.png")])
        with self.assertRaisesRegex(ValueError, "asset_id values must be unique"):
            _validate_manifest(data)

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "round"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "escapes its authorized root"):
                _safe_child(root, "../outside.png", "source_path")

    def test_valid_48px_asset_is_copied_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            round_dir = root / "round"
            source_dir = round_dir / "sources"
            output_dir = root / "out"
            source_dir.mkdir(parents=True)

            source = source_dir / "test.png"
            Image.new("RGBA", (48, 48), (10, 20, 30, 255)).save(source, format="PNG")
            original = source.read_bytes()

            manifest_path = round_dir / "manifest.json"
            manifest_path.write_text(json.dumps(self._manifest()), encoding="utf-8")

            report = process_manifest(str(manifest_path), str(output_dir))
            output = output_dir / "tideglass" / "test.png"

            self.assertEqual(original, output.read_bytes())
            self.assertEqual(report["assets"][0]["size"], [48, 48])
            self.assertFalse(report["pixels_resized"])
            self.assertFalse(report["gpu_used"])
            self.assertFalse(report["generator_used"])

    def test_valid_96px_asset_requires_2x2_footprint(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            round_dir = root / "round"
            source_dir = round_dir / "sources"
            output_dir = root / "out"
            source_dir.mkdir(parents=True)

            source = source_dir / "test.png"
            Image.new("RGB", (96, 96), (40, 50, 60)).save(source, format="PNG")

            asset = self._asset(footprint_tiles=[2, 2])
            manifest_path = round_dir / "manifest.json"
            manifest_path.write_text(json.dumps(self._manifest([asset])), encoding="utf-8")

            report = process_manifest(str(manifest_path), str(output_dir))
            self.assertEqual(report["assets"][0]["size"], [96, 96])
            self.assertEqual(report["assets"][0]["footprint_tiles"], [2, 2])

    def test_dimension_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            round_dir = root / "round"
            source_dir = round_dir / "sources"
            output_dir = root / "out"
            source_dir.mkdir(parents=True)

            source = source_dir / "test.png"
            Image.new("RGBA", (96, 96), (10, 20, 30, 255)).save(source, format="PNG")

            manifest_path = round_dir / "manifest.json"
            manifest_path.write_text(json.dumps(self._manifest()), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "do not match declared footprint"):
                process_manifest(str(manifest_path), str(output_dir))


if __name__ == "__main__":
    unittest.main()
