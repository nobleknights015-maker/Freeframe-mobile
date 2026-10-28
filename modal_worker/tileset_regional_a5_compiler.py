"""Deterministic zero-GPU compiler for Plushbound regional A5 tilesets.

Consumes one region's eight accepted 384x384 source masters plus a banked source
closeout, derives exactly sixteen 48x48 variants per material, and assembles the
locked Engine v1 A5 geometry: 8x16 tiles / 384x768 RGBA PNG.

This module never calls a generation provider or GPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops

from modal_worker.asset_profiles import validate_metadata
from modal_worker.tileset_source_normalizer import (
    MAX_EDGE_DISCONTINUITY,
    MIN_RGB_STDDEV,
    edge_discontinuity,
    normalize_image,
    rgb_stddev,
)

TILE_SIZE = 48
SHEET_WIDTH = 384
SHEET_HEIGHT = 768
COLUMNS = 8
ROWS = 16
SLOT_COUNT = 128
VARIANTS_PER_MATERIAL = 16
SOURCE_SIZE = (384, 384)
ENGINE_PROFILE = "mv_tileset_a5"
SCOPE_MANIFEST_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _variant_offsets() -> list[tuple[int, int]]:
    offsets = [(x * 96, y * 96) for y in range(4) for x in range(4)]
    if len(offsets) != VARIANTS_PER_MATERIAL or len(set(offsets)) != VARIANTS_PER_MATERIAL:
        raise RuntimeError("expected exactly sixteen unique deterministic wrap offsets")
    return offsets


def _load_scope(region: str) -> tuple[dict, dict]:
    data = json.loads(SCOPE_MANIFEST_PATH.read_text(encoding="utf-8"))
    if data["schema"] != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("unexpected regional A5 scope schema")
    if region == "elyndor":
        raise RuntimeError("Elyndor A5 is closed/banked and may not be recompiled by the regional pipeline")
    if region not in data["remaining_regions"] or region not in data["regions"]:
        raise RuntimeError(f"region is not an unfinished regional A5 scope: {region}")
    if data["spend_gate"]["catalog_wide_launch_authorized"] is not False:
        raise RuntimeError("catalog-wide launch gate changed unexpectedly")
    scope = data["regions"][region]
    if scope["sheet_type"] != "A5":
        raise RuntimeError("regional scope is not A5")
    if scope["stable_sheet_id"] != f"tileset.{region}.a5":
        raise RuntimeError("regional stable sheet ID mismatch")
    materials = scope["materials"]
    if len(materials) != 8 or len(set(materials)) != 8:
        raise RuntimeError("regional A5 requires exactly eight unique material families")
    if not all(isinstance(material, str) and material and material.replace("_", "").replace("-", "").isalnum() for material in materials):
        raise RuntimeError("regional A5 material key is invalid")
    return data, scope


def self_test(region: str) -> dict:
    data, scope = _load_scope(region)
    contract = data["engine_contract"]
    if contract["profile"] != ENGINE_PROFILE:
        raise RuntimeError("Engine profile mismatch")
    if contract["sheet_size"] != [SHEET_WIDTH, SHEET_HEIGHT]:
        raise RuntimeError("A5 sheet geometry mismatch")
    if contract["tile_size"] != [TILE_SIZE, TILE_SIZE]:
        raise RuntimeError("A5 tile geometry mismatch")
    if contract["grid"] != [COLUMNS, ROWS] or contract["slot_count"] != SLOT_COUNT:
        raise RuntimeError("A5 grid/slot contract mismatch")
    if data["source_contract"]["variants_per_material"] != VARIANTS_PER_MATERIAL:
        raise RuntimeError("variant count contract mismatch")

    offsets = _variant_offsets()
    slots = []
    for family_index, material_key in enumerate(scope["materials"]):
        for variant_index, offset in enumerate(offsets):
            absolute_slot = family_index * VARIANTS_PER_MATERIAL + variant_index
            row, column = divmod(absolute_slot, COLUMNS)
            slots.append((material_key, variant_index, absolute_slot, row, column, offset))
    if len(slots) != SLOT_COUNT:
        raise RuntimeError("deterministic slot planner did not produce exactly 128 slots")
    if len({row[2] for row in slots}) != SLOT_COUNT:
        raise RuntimeError("deterministic slot planner produced duplicate slots")
    if min(row[3] for row in slots) != 0 or max(row[3] for row in slots) != ROWS - 1:
        raise RuntimeError("deterministic slot planner row bounds mismatch")
    if min(row[4] for row in slots) != 0 or max(row[4] for row in slots) != COLUMNS - 1:
        raise RuntimeError("deterministic slot planner column bounds mismatch")
    return {
        "status": "PASS",
        "region": region,
        "stable_sheet_id": scope["stable_sheet_id"],
        "sheet_size": [SHEET_WIDTH, SHEET_HEIGHT],
        "tile_size": [TILE_SIZE, TILE_SIZE],
        "grid": [COLUMNS, ROWS],
        "slot_count": SLOT_COUNT,
        "material_family_count": len(scope["materials"]),
        "variants_per_material": VARIANTS_PER_MATERIAL,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
    }


def _load_source_closeout(region: str, path: Path, scope: dict) -> dict[str, str]:
    closeout = json.loads(path.read_text(encoding="utf-8"))
    if closeout.get("schema") != "plushbound.tileset_regional_a5_source_closeout.v1":
        raise RuntimeError("unexpected regional A5 source closeout schema")
    if closeout.get("region") != region or closeout.get("target_sheet_type") != "A5":
        raise RuntimeError("regional source closeout target mismatch")
    if closeout.get("status") != "CLOSED_GREEN_8_OF_8":
        raise RuntimeError("regional source closeout is not closed green 8/8")
    if closeout.get("machine_gate") != "PASS_8_OF_8" or closeout.get("manual_visual_gate") != "PASS_8_OF_8":
        raise RuntimeError("regional source closeout has not passed both machine and visual gates")
    if closeout.get("accepted_source_ids_protected_from_rerender") is not True:
        raise RuntimeError("accepted source IDs are not protected")
    if closeout.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("catalog-wide launch unexpectedly authorized")

    expected_ids = {f"tileset.{region}.a5.source.{material_key}" for material_key in scope["materials"]}
    hashes = {row["asset_id"]: row["raw_sha256"] for row in closeout.get("sources", [])}
    if set(hashes) != expected_ids:
        raise RuntimeError("source closeout does not contain the exact eight regional source IDs")
    return hashes


def compile_sheet(region: str, source_root: Path, source_closeout: Path, output_dir: Path) -> dict:
    _, scope = _load_scope(region)
    source_hashes = _load_source_closeout(region, source_closeout, scope)
    output_dir.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGBA", (SHEET_WIDTH, SHEET_HEIGHT), (0, 0, 0, 0))
    offsets = _variant_offsets()
    all_variant_hashes: list[str] = []
    family_reports: list[dict] = []

    for family_index, material_key in enumerate(scope["materials"]):
        material_key = str(material_key)
        asset_id = f"tileset.{region}.a5.source.{material_key}"
        source_path = source_root / f"{material_key}-384.png"
        if not source_path.is_file():
            raise RuntimeError(f"missing banked source master: {source_path}")
        source_hash = _sha256(source_path)
        if source_hash != source_hashes[asset_id]:
            raise RuntimeError(f"{asset_id}: source hash mismatch")
        with Image.open(source_path) as source_image:
            base = source_image.convert("RGBA")
        if base.size != SOURCE_SIZE:
            raise RuntimeError(f"{asset_id}: expected {SOURCE_SIZE}, got {base.size}")

        family_hashes: list[str] = []
        slots: list[dict] = []
        for variant_index, (offset_x, offset_y) in enumerate(offsets):
            tile = normalize_image(ImageChops.offset(base, offset_x, offset_y))
            edge = edge_discontinuity(tile)
            stddev = rgb_stddev(tile)
            if edge > MAX_EDGE_DISCONTINUITY:
                raise RuntimeError(
                    f"{asset_id} variant {variant_index}: edge discontinuity "
                    f"{edge:.6f} exceeds {MAX_EDGE_DISCONTINUITY}"
                )
            if stddev < MIN_RGB_STDDEV:
                raise RuntimeError(
                    f"{asset_id} variant {variant_index}: rgb stddev "
                    f"{stddev:.4f} below {MIN_RGB_STDDEV}"
                )
            tile_hash = hashlib.sha256(tile.tobytes()).hexdigest()
            family_hashes.append(tile_hash)
            all_variant_hashes.append(tile_hash)
            absolute_slot = family_index * VARIANTS_PER_MATERIAL + variant_index
            row, column = divmod(absolute_slot, COLUMNS)
            sheet.alpha_composite(tile, (column * TILE_SIZE, row * TILE_SIZE))
            slots.append({
                "variant": variant_index,
                "slot": absolute_slot,
                "row": row,
                "column": column,
                "source_wrap_offset": [offset_x, offset_y],
                "edge_discontinuity": round(edge, 6),
                "rgb_stddev": round(stddev, 4),
                "tile_sha256_rgba": tile_hash,
            })
        if len(set(family_hashes)) != VARIANTS_PER_MATERIAL:
            raise RuntimeError(f"{asset_id}: deterministic variant generation produced duplicates")
        family_reports.append({
            "material_key": material_key,
            "source_asset_id": asset_id,
            "source_sha256": source_hash,
            "variant_count": VARIANTS_PER_MATERIAL,
            "unique_variant_count": len(set(family_hashes)),
            "maximum_edge_discontinuity": round(max(row["edge_discontinuity"] for row in slots), 6),
            "minimum_rgb_stddev": round(min(row["rgb_stddev"] for row in slots), 4),
            "slots": slots,
        })

    if len(all_variant_hashes) != SLOT_COUNT or len(set(all_variant_hashes)) != SLOT_COUNT:
        raise RuntimeError("compiled regional A5 slot count/uniqueness mismatch")

    safe_region = region.replace("-", "_")
    sheet_path = output_dir / f"{safe_region}_A5.png"
    sheet.save(sheet_path, format="PNG")
    with Image.open(sheet_path) as image:
        image.load()
        engine_validation = validate_metadata(
            profile_name=ENGINE_PROFILE,
            fmt=str(image.format or ""),
            width=image.width,
            height=image.height,
            has_alpha="A" in image.getbands(),
        )
    if not engine_validation["valid"]:
        raise RuntimeError(
            "compiled A5 failed repository engine profile: "
            + "; ".join(engine_validation["errors"])
        )

    report = {
        "schema": "plushbound.regional_a5_compile_report.v1",
        "status": "PASS_NO_SPEND_DETERMINISTIC_COMPILE_ENGINE_PROFILE",
        "region": region,
        "stable_sheet_id": scope["stable_sheet_id"],
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "engine_profile": ENGINE_PROFILE,
        "engine_profile_validation": engine_validation,
        "sheet_path": str(sheet_path),
        "sheet_sha256": _sha256(sheet_path),
        "sheet_width": SHEET_WIDTH,
        "sheet_height": SHEET_HEIGHT,
        "tile_size": TILE_SIZE,
        "columns": COLUMNS,
        "rows": ROWS,
        "slot_count": SLOT_COUNT,
        "material_family_count": len(scope["materials"]),
        "unique_slot_hashes": len(set(all_variant_hashes)),
        "manual_visual_contact_sheet_required": True,
        "engine_v1_compatibility_contract_check_required": True,
        "runtime_import_proof": False,
        "catalog_wide_launch_authorized": False,
        "families": family_reports,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--source-closeout", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(args.region), indent=2, sort_keys=True))
        return
    if args.source_root is None or args.source_closeout is None or args.output_dir is None:
        parser.error("--source-root, --source-closeout and --output-dir are required unless --self-test is used")
    report = compile_sheet(args.region, args.source_root, args.source_closeout, args.output_dir)
    print(json.dumps({k: v for k, v in report.items() if k != "families"}, sort_keys=True))


if __name__ == "__main__":
    main()
