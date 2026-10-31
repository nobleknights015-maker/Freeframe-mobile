from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from modal_worker.approved_art_source_attestation import create_attestation, verify_attestation


class ApprovedSourceAttestationTests(unittest.TestCase):
    def _round(self, root: Path) -> Path:
        round_dir = root / "round"
        source_dir = round_dir / "sources"
        source_dir.mkdir(parents=True)
        Image.new("RGBA", (96, 96), (11, 22, 33, 255)).save(source_dir / "dock_timber.png", format="PNG")
        manifest = {
            "schema": "plushbound.approved_art_round.v1",
            "round_id": "test",
            "provenance": "vera-chatgpt-approved",
            "generator_calls_allowed": False,
            "gpu_allowed": False,
            "assets": [{
                "asset_id": "tideglass.dock_timber",
                "source_path": "sources/dock_timber.png",
                "footprint_tiles": [2, 2],
                "output_name": "tideglass/dock_timber.png",
                "approval_status": "approved",
                "approval_designation": "VERA_APPROVED_SOURCE_V1",
                "production_authorized": True,
                "provenance": "vera-chatgpt-approved",
            }],
        }
        path = round_dir / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_attestation_binds_exact_source_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = self._round(Path(td))
            attestation = create_attestation(manifest, "tideglass.dock_timber")
            self.assertEqual(len(attestation["source_sha256"]), 64)
            attestation_path = Path(td) / "attestation.json"
            attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
            verified = verify_attestation(manifest, attestation_path)
            self.assertEqual(verified["source_sha256"], attestation["source_sha256"])

    def test_replacement_at_same_filename_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = self._round(root)
            attestation = create_attestation(manifest, "tideglass.dock_timber")
            attestation_path = root / "attestation.json"
            attestation_path.write_text(json.dumps(attestation), encoding="utf-8")
            Image.new("RGBA", (96, 96), (200, 100, 50, 255)).save(
                manifest.parent / "sources" / "dock_timber.png", format="PNG"
            )
            with self.assertRaisesRegex(ValueError, "attestation mismatch"):
                verify_attestation(manifest, attestation_path)

    def test_wrong_dimensions_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest = self._round(root)
            Image.new("RGBA", (48, 48), (1, 2, 3, 255)).save(
                manifest.parent / "sources" / "dock_timber.png", format="PNG"
            )
            with self.assertRaisesRegex(ValueError, "must be 96x96"):
                create_attestation(manifest, "tideglass.dock_timber")

    def test_missing_source_fails(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = self._round(Path(td))
            (manifest.parent / "sources" / "dock_timber.png").unlink()
            with self.assertRaises(FileNotFoundError):
                create_attestation(manifest, "tideglass.dock_timber")


if __name__ == "__main__":
    unittest.main()
