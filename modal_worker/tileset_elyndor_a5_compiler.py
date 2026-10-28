"""Deterministic no-spend compiler for the locked Elyndor A5 source language.

Consumes the eight exact banked 384x384 source masters, verifies their hashes,
derives 16 seam-safe 48x48 variants per material, and assembles the repository's
runtime A5 profile: 8x16 tiles / 384x768 RGBA PNG. No provider or GPU calls.
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
VARIANTS_PER_MATERIAL = 16
SOURCE_SIZE = (384, 384)
ENGINE_PROFILE = "mv_tileset_a5"
CLOSEOUT_PATH = Path("modal_worker/tileset_source_canary_closeout.json")
CONTRACT_PATH = Path("modal_worker/tileset_elyndor_a5_expansion_contract.json")
MATERIAL_ORDER = (
    "lush_grass",
    "wildflower_grass",
    "warm_soil",
    "dirt_path",
    "tilled_farm_soil",
    "pale_field_stone",
    "village_timber",
    "straw_thatch",
)
ASSET_ID_BY_MATERIAL = {key: f"tileset.elyndor.a5.source.{key}" for key in MATERIAL_ORDER}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _variant_offsets() -> list[tuple[int, int]]:
    offsets = [(x * 96, y * 96) for y in range(4) for x in range(4)]
    if len(offsets) != VARIANTS_PER_MATERIAL or len(set(offsets)) != VARIANTS_PER_MATERIAL:
        raise RuntimeError("expected exactly 16 unique deterministic wrap offsets")
    return offsets


def _load_contracts() -> tuple[dict, dict, dict[str, str]]:
    closeout = json.loads(CLOSEOUT_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if closeout["schema"] != "plushbound.tileset_source_canary_closeout.v1":
        raise RuntimeError("unexpected tileset source closeout schema")
    if closeout["status"] != "CLOSED_GREEN_8_OF_8":
        raise RuntimeError("Elyndor source language is not closed green 8/8")
    if closeout["machine_gate"] != "PASS_8_OF_8" or closeout["manual_visual_gate"] != "PASS_8_OF_8":
        raise RuntimeError("Elyndor source language has not passed both machine and visual gates")
    if closeout["accepted_source_ids_protected_from_rerender"] is not True:
        raise RuntimeError("accepted source protection must remain enabled")
    if contract["schema"] != "plushbound.tileset_elyndor_a5_expansion_contract.v2":
        raise RuntimeError("unexpected Elyndor A5 expansion contract schema")
    if contract["status"] != "DESIGN_ONLY_NO_SPEND_ENGINE_PROFILE_CORRECTED":
        raise RuntimeError("A5 contract must remain corrected no-spend design only")
    if contract["provider_calls_authorized"] != 0 or contract["gpu_calls_authorized"] != 0 or contract["generation_jobs_authorized"] != 0:
        raise RuntimeError("A5 deterministic compile contract unexpectedly authorizes paid work")
    if contract["engine_profile"] != ENGINE_PROFILE:
        raise RuntimeError("A5 engine profile changed")
    if [contract["sheet_width"], contract["sheet_height"]] != [SHEET_WIDTH, SHEET_HEIGHT]:
        raise RuntimeError("A5 sheet geometry changed")
    if contract["engine_tile_size"] != TILE_SIZE or contract["slot_count"] != COLUMNS * ROWS:
        raise RuntimeError("A5 tile geometry changed")

    source_hashes = {row["asset_id"]: row["raw_sha256"] for row in closeout["sources"]}
    if set(source_hashes) != set(ASSET_ID_BY_MATERIAL.values()):
        raise RuntimeError("source closeout does not contain the exact eight Elyndor IDs")
    return closeout, contract, source_hashes


def compile_sheet(source_root: Path, output_dir: Path) -> dict:
    _, contract, source_hashes = _load_contracts()
    output_dir.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGBA", (SHEET_WIDTH, SHEET_HEIGHT), (0, 0, 0, 0))
    offsets = _variant_offsets()
    all_variant_hashes: list[str] = []
    family_reports: list[dict] = []

    for family_index, material in enumerate(MATERIAL_ORDER):
        asset_id = ASSET_ID_BY_MATERIAL[material]
        source_path = source_root / f"{material}-384.png"
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
                raise RuntimeError(f"{asset_id} variant {variant_index}: edge discontinuity {edge:.6f} exceeds {MAX_EDGE_DISCONTINUITY}")
            if stddev < MIN_RGB_STDDEV:
                raise RuntimeError(f"{asset_id} variant {variant_index}: rgb stddev {stddev:.4f} below {MIN_RGB_STDDEV}")
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
            "material_key": material,
            "source_asset_id": asset_id,
            "source_sha256": source_hash,
            "variant_count": VARIANTS_PER_MATERIAL,
            "unique_variant_count": len(set(family_hashes)),
            "maximum_edge_discontinuity": round(max(row["edge_discontinuity"] for row in slots), 6),
            "minimum_rgb_stddev": round(min(row["rgb_stddev"] for row in slots), 4),
            "slots": slots,
        })

    if sheet.size != (SHEET_WIDTH, SHEET_HEIGHT):
        raise RuntimeError("compiled A5 sheet geometry mismatch")
    if len(all_variant_hashes) != COLUMNS * ROWS or len(set(all_variant_hashes)) != COLUMNS * ROWS:
        raise RuntimeError("compiled A5 sheet slot count/uniqueness mismatch")

    sheet_path = output_dir / "Elyndor_A5.png"
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
        raise RuntimeError("compiled A5 failed repository engine profile: " + "; ".join(engine_validation["errors"]))

    report = {
        "schema": "plushbound.elyndor_a5_compile_report.v2",
        "status": "PASS_NO_SPEND_DETERMINISTIC_COMPILE_ENGINE_PROFILE",
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
        "slot_count": COLUMNS * ROWS,
        "material_family_count": len(MATERIAL_ORDER),
        "unique_slot_hashes": len(set(all_variant_hashes)),
        "manual_visual_contact_sheet_required": contract["validation_requirements"]["manual_visual_contact_sheet_required"],
        "engine_v1_compatibility_contract_check_required": contract["validation_requirements"]["engine_v1_compatibility_contract_check_required"],
        "families": family_reports,
    }
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = compile_sheet(args.source_root, args.output_dir)
    print(json.dumps({k: v for k, v in report.items() if k != "families"}, sort_keys=True))


if __name__ == "__main__":
    main()
