"""Fail-closed compatibility validator for Plushbound Engine v1 A5 sheet bytes.

This is deliberately a geometry/profile check only. The repository does not contain
a live World Editor/Engine v1 importer, and pixel uniqueness is not a layout proof:
valid WORLD_TILE_ASSET_V1 packages may contain explicit empty, covered, or repeated
visual cells. Production handoff must additionally pass world_editor_tile_ingest_gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from modal_worker.asset_profiles import validate_metadata

PROFILE = "mv_tileset_a5"
TILE_SIZE = 48
EXPECTED_WIDTH = 384
EXPECTED_HEIGHT = 768
EXPECTED_COLUMNS = 8
EXPECTED_ROWS = 16
EXPECTED_SLOTS = 128


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_a5(sheet_path: Path, *, expected_sha256: str | None = None) -> dict:
    if not sheet_path.is_file():
        raise RuntimeError(f"missing A5 sheet: {sheet_path}")
    digest = _sha256(sheet_path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise RuntimeError(f"A5 hash mismatch: {digest} != {expected_sha256}")

    with Image.open(sheet_path) as image:
        image.load()
        fmt = str(image.format or "")
        width, height = image.size
        has_alpha = "A" in image.getbands()

    profile_validation = validate_metadata(
        profile_name=PROFILE,
        fmt=fmt,
        width=width,
        height=height,
        has_alpha=has_alpha,
    )
    if not profile_validation["valid"]:
        raise RuntimeError("A5 failed repository engine profile: " + "; ".join(profile_validation["errors"]))
    if [width, height] != [EXPECTED_WIDTH, EXPECTED_HEIGHT]:
        raise RuntimeError("A5 geometry differs from locked Engine v1 compatibility contract")
    if width % TILE_SIZE or height % TILE_SIZE:
        raise RuntimeError("A5 dimensions are not divisible by the 48px engine tile size")

    columns, rows = width // TILE_SIZE, height // TILE_SIZE
    if [columns, rows] != [EXPECTED_COLUMNS, EXPECTED_ROWS]:
        raise RuntimeError("A5 grid is not the locked 8x16 layout")
    slot_count = columns * rows
    if slot_count != EXPECTED_SLOTS:
        raise RuntimeError("A5 slot count mismatch")

    return {
        "schema": "plushbound.engine_v1_a5_compatibility_report.v2",
        "status": "PASS_ENGINE_V1_COMPATIBILITY_CONTRACT",
        "proof_scope": "sheet-byte profile and geometry compatibility only; manifest/package handoff gate still required",
        "runtime_import_proof": False,
        "world_editor_handoff_gate_required": True,
        "pixel_uniqueness_used_as_layout_proof": False,
        "profile": PROFILE,
        "profile_validation": profile_validation,
        "format": fmt.upper(),
        "has_alpha": has_alpha,
        "sheet_sha256": digest,
        "sheet_width": width,
        "sheet_height": height,
        "tile_size": TILE_SIZE,
        "columns": columns,
        "rows": rows,
        "slot_count": slot_count,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", type=Path, required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    print(json.dumps(validate_a5(args.sheet, expected_sha256=args.expected_sha256), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
