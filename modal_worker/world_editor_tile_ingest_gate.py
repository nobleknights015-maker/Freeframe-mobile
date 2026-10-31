"""Fail-closed WORLD_TILE_ASSET_V1 handoff gate for World Editor / Engine v1.

The repository does not contain the live World Editor importer. This module is the
canonical repository-side acceptance boundary for a compiled tile package. It does
not alter pixels, infer layout, or claim live runtime-import proof.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from typing import Mapping

from PIL import Image

from modal_worker.a5_tilesheet_compiler import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    COLUMNS,
    COMPILER_VERSION,
    ROWS,
    SCHEMA,
    SLOT_COUNT,
    TEMPLATE_VERSION,
    TILE_SIZE,
    validate_world_tile_manifest,
)
from modal_worker.asset_profiles import validate_metadata

HANDOFF_SCHEMA = "plushbound.world_editor_tile_handoff.v1"
PROFILE = "mv_tileset_a5"
AUTHORIZED_COMPILERS = {COMPILER_VERSION}


def _canonical_manifest_bytes(manifest: Mapping[str, object]) -> bytes:
    return json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _require_metadata(metadata: Mapping[str, object], field: str, expected: object) -> None:
    if metadata.get(field) != expected:
        raise ValueError(f"compiler metadata {field} must be exactly {expected!r}")


def validate_world_editor_handoff(
    png: bytes,
    manifest: Mapping[str, object],
    metadata: Mapping[str, object],
) -> dict[str, object]:
    """Validate one immutable compiled package before World Editor handoff."""
    validate_world_tile_manifest(manifest)

    compiler_version = metadata.get("compiler_version")
    if compiler_version not in AUTHORIZED_COMPILERS:
        raise ValueError(f"unauthorized compiler_version: {compiler_version!r}")

    exact_metadata = {
        "schema": SCHEMA,
        "template_version": TEMPLATE_VERSION,
        "format": "PNG",
        "width": CANVAS_WIDTH,
        "height": CANVAS_HEIGHT,
        "tile_width": TILE_SIZE,
        "tile_height": TILE_SIZE,
        "columns": COLUMNS,
        "rows": ROWS,
        "slot_count": SLOT_COUNT,
        "grid_origin": [0, 0],
        "margins": 0,
        "padding": 0,
        "resized_after_generation": False,
        "layout_inferred_visually": False,
        "reference_sheet_pixels_used_as_runtime_art": False,
    }
    for field, expected in exact_metadata.items():
        _require_metadata(metadata, field, expected)

    png_sha256 = hashlib.sha256(png).hexdigest()
    if metadata.get("png_sha256") != png_sha256:
        raise ValueError("compiled PNG hash does not match compiler metadata")

    manifest_sha256 = hashlib.sha256(_canonical_manifest_bytes(manifest)).hexdigest()
    if metadata.get("manifest_sha256") != manifest_sha256:
        raise ValueError("manifest hash does not match compiler metadata")

    expected_asset_ids = {
        row["asset_id"]
        for row in manifest["slots"]  # type: ignore[index]
        if isinstance(row, dict) and isinstance(row.get("asset_id"), str)
    }
    source_hashes = metadata.get("source_png_sha256")
    if not isinstance(source_hashes, dict) or set(source_hashes) != expected_asset_ids:
        raise ValueError("source hash ledger must exactly match manifest anchor asset IDs")
    for asset_id, digest in source_hashes.items():
        if not isinstance(asset_id, str) or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("source hash ledger contains an invalid SHA-256 entry")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError("source hash ledger contains a non-hex SHA-256 entry") from exc

    try:
        with Image.open(io.BytesIO(png)) as image:
            image.load()
            fmt = str(image.format or "")
            width, height = image.size
            has_alpha = "A" in image.getbands()
            mode = image.mode
    except OSError as exc:
        raise ValueError("compiled runtime payload is not a valid PNG") from exc

    profile = validate_metadata(
        profile_name=PROFILE,
        fmt=fmt,
        width=width,
        height=height,
        has_alpha=has_alpha,
    )
    if not profile["valid"]:
        raise ValueError("compiled PNG failed Engine v1 asset profile: " + "; ".join(profile["errors"]))
    if mode not in {"RGBA", "RGB"}:
        raise ValueError(f"compiled PNG mode must be RGB or RGBA; got {mode}")
    if (width, height) != (CANVAS_WIDTH, CANVAS_HEIGHT):
        raise ValueError("compiled PNG geometry differs from locked WORLD_TILE_ASSET_V1")

    return {
        "schema": HANDOFF_SCHEMA,
        "status": "ACCEPTED_FOR_WORLD_EDITOR_HANDOFF",
        "world_editor_must_consume_manifest": True,
        "visual_layout_inference_allowed": False,
        "automatic_repair_allowed": False,
        "runtime_import_proof": False,
        "proof_scope": "repository-side package integrity and Engine v1 compatibility only",
        "sheet_id": manifest["sheet_id"],
        "material_id": manifest["material_id"],
        "compiler_version": compiler_version,
        "png_sha256": png_sha256,
        "manifest_sha256": manifest_sha256,
        "slot_count": SLOT_COUNT,
        "profile": PROFILE,
        "profile_validation": profile,
    }


def validate_package_files(png_path: Path, manifest_path: Path, metadata_path: Path) -> dict[str, object]:
    if not png_path.is_file() or not manifest_path.is_file() or not metadata_path.is_file():
        raise ValueError("World Editor handoff requires PNG, manifest JSON, and compiler metadata JSON")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(metadata, dict):
        raise ValueError("manifest and compiler metadata must be JSON objects")
    return validate_world_editor_handoff(png_path.read_bytes(), manifest, metadata)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate_package_files(args.png, args.manifest, args.metadata), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
