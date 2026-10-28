"""Deterministic A5 handoff bridge for World Asset Pipeline V2.

This stages a compiler-approved A5 PNG into an engine-facing package, records a
stable 8x16 slot manifest, and proves a byte-identical round trip. The repository
currently has no live World Editor/Engine v1 A5 importer, so this module MUST NOT
claim live runtime-import proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from PIL import Image

from modal_worker.engine_v1_a5_compatibility_validator import (
    EXPECTED_COLUMNS,
    EXPECTED_HEIGHT,
    EXPECTED_ROWS,
    EXPECTED_SLOTS,
    EXPECTED_WIDTH,
    PROFILE,
    TILE_SIZE,
    validate_a5,
)

SCHEMA = "plushbound.world_asset_pipeline_v2_a5_import_bridge.v1"
STATUS = "PASS_ENGINE_FACING_A5_IMPORT_BRIDGE"
_STABLE_ID = re.compile(r"^tileset\.([a-z0-9-]+)\.a5$")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _slot_manifest(sheet_path: Path) -> list[dict]:
    with Image.open(sheet_path) as image:
        rgba = image.convert("RGBA")
        rows: list[dict] = []
        for row in range(EXPECTED_ROWS):
            for column in range(EXPECTED_COLUMNS):
                index = row * EXPECTED_COLUMNS + column
                box = (
                    column * TILE_SIZE,
                    row * TILE_SIZE,
                    (column + 1) * TILE_SIZE,
                    (row + 1) * TILE_SIZE,
                )
                tile = rgba.crop(box)
                rows.append({
                    "slot_index": index,
                    "row": row,
                    "column": column,
                    "x": box[0],
                    "y": box[1],
                    "width": TILE_SIZE,
                    "height": TILE_SIZE,
                    "pixel_sha256": hashlib.sha256(tile.tobytes()).hexdigest(),
                })
    if len(rows) != EXPECTED_SLOTS or len({r["pixel_sha256"] for r in rows}) != EXPECTED_SLOTS:
        raise RuntimeError("A5 import bridge requires 128 unique deterministic slots")
    return rows


def stage_a5(
    sheet_path: Path,
    stable_sheet_id: str,
    output_root: Path,
    *,
    expected_sha256: str | None = None,
) -> dict:
    match = _STABLE_ID.fullmatch(stable_sheet_id)
    if not match:
        raise RuntimeError("stable_sheet_id must match tileset.<region>.a5")
    region = match.group(1)

    validation = validate_a5(sheet_path, expected_sha256=expected_sha256)
    if validation["status"] != "PASS_ENGINE_V1_COMPATIBILITY_CONTRACT":
        raise RuntimeError("A5 import bridge requires Engine v1 compatibility PASS")

    package_root = output_root / stable_sheet_id
    tileset_dir = package_root / "tilesets"
    tileset_dir.mkdir(parents=True, exist_ok=True)
    staged_path = tileset_dir / f"{region}_A5.png"
    shutil.copyfile(sheet_path, staged_path)

    source_sha = _sha(sheet_path)
    staged_sha = _sha(staged_path)
    if source_sha != staged_sha:
        raise RuntimeError("A5 changed bytes while crossing import bridge")

    roundtrip = validate_a5(staged_path, expected_sha256=source_sha)
    slots = _slot_manifest(staged_path)
    manifest = {
        "schema": SCHEMA,
        "status": STATUS,
        "proof_scope": "deterministic engine-facing staging, slot mapping and byte-identical round trip; not live World Editor/Engine runtime import",
        "runtime_import_proof": False,
        "live_importer_present_in_repository": False,
        "stable_sheet_id": stable_sheet_id,
        "region": region,
        "profile": PROFILE,
        "source_path": str(sheet_path),
        "staged_relative_path": str(staged_path.relative_to(package_root)),
        "source_sha256": source_sha,
        "staged_sha256": staged_sha,
        "byte_identity_preserved": True,
        "format": "PNG",
        "mode": "RGBA",
        "sheet_size": [EXPECTED_WIDTH, EXPECTED_HEIGHT],
        "tile_size": [TILE_SIZE, TILE_SIZE],
        "grid": [EXPECTED_COLUMNS, EXPECTED_ROWS],
        "slot_count": EXPECTED_SLOTS,
        "unique_slot_hashes": EXPECTED_SLOTS,
        "engine_profile_validation": validation,
        "roundtrip_validation": roundtrip,
        "slots": slots,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "catalog_wide_launch_authorized": False,
    }
    (package_root / "import-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def _fixture(path: Path) -> None:
    image = Image.new("RGBA", (EXPECTED_WIDTH, EXPECTED_HEIGHT), (0, 0, 0, 255))
    for index in range(EXPECTED_SLOTS):
        row, column = divmod(index, EXPECTED_COLUMNS)
        base = ((index * 37) % 256, (index * 73) % 256, (index * 109) % 256, 255)
        tile = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), base)
        # Encode the slot index into deterministic corner pixels so all 128
        # slots remain unique even if base colors collide.
        tile.putpixel((0, 0), (index, 255 - index, (index * 3) % 256, 255))
        tile.putpixel((TILE_SIZE - 1, TILE_SIZE - 1), ((index * 5) % 256, index, 255 - index, 255))
        image.paste(tile, (column * TILE_SIZE, row * TILE_SIZE))
    image.save(path, format="PNG")


def self_test() -> dict:
    with tempfile.TemporaryDirectory(prefix="plushbound-a5-import-bridge-") as temp:
        root = Path(temp)
        source = root / "fixture.png"
        _fixture(source)
        result = stage_a5(source, "tileset.bridge-test.a5", root / "package")
        if result["source_sha256"] != result["staged_sha256"]:
            raise RuntimeError("bridge self-test lost byte identity")
        if result["slot_count"] != 128 or result["unique_slot_hashes"] != 128:
            raise RuntimeError("bridge self-test lost A5 slot identity")
        return {
            "schema": "plushbound.world_asset_pipeline_v2_a5_import_bridge_self_test.v1",
            "status": "PASS_ZERO_GPU_A5_IMPORT_BRIDGE_ROUNDTRIP",
            "profile": PROFILE,
            "byte_identity_preserved": True,
            "slot_count": 128,
            "unique_slot_hashes": 128,
            "provider_calls": 0,
            "gpu_calls": 0,
            "generation_calls": 0,
            "runtime_import_proof": False,
            "live_importer_present_in_repository": False,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", type=Path)
    parser.add_argument("--stable-sheet-id")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    else:
        if args.sheet is None or not args.stable_sheet_id or args.output_root is None:
            parser.error("bridge requires --sheet, --stable-sheet-id and --output-root")
        result = stage_a5(
            args.sheet,
            args.stable_sheet_id,
            args.output_root,
            expected_sha256=args.expected_sha256,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
