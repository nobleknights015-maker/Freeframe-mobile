"""Validate Plushbound Vera single-asset world-tile generation contracts.

This validator protects the pre-generation design boundary. It does not generate
images. It rejects ambiguous or assortment-style requests before visual work.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "plushbound.vera_world_tile_generation_contract.v1"
BATCH_SCHEMA = "plushbound.vera_world_tile_generation_batch.v1"
CONTRACT_ID = "VERA_WORLD_TILE_GENERATION_V1"
ALLOWED_FOOTPRINTS = {(1, 1): (48, 48), (2, 2): (96, 96)}
REQUIRED_TARGET_FIELDS = {
    "asset_id",
    "visual_function",
    "runtime_role",
    "footprint_tiles",
    "pixel_size",
    "top_down_required",
    "tileable_required",
    "required_elements",
    "forbidden_elements",
    "original_plushbound_art_required",
}
FORBIDDEN_COMPOSITION_TERMS = {
    "assortment",
    "asset sheet",
    "showcase sheet",
    "variety sheet",
    "collection of tiles",
    "multiple materials",
    "mixed props",
    "scene composition",
}


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise ValueError("unsupported Vera generation contract schema")
    if contract.get("contract_id") != CONTRACT_ID:
        raise ValueError("unexpected Vera generation contract id")

    exact_false = [
        "external_reference_pixels_allowed_in_output",
        "sheet_generation_allowed",
        "showcase_composition_allowed",
        "assortment_composition_allowed",
        "scene_composition_allowed",
        "labels_text_borders_guides_allowed",
        "decorative_extras_allowed_unless_asset_function_requires_them",
    ]
    for field in exact_false:
        if contract.get(field) is not False:
            raise ValueError(f"{field} must be false")

    for field in ("one_asset_id_per_generation", "one_visual_function_per_generation"):
        if contract.get(field) is not True:
            raise ValueError(f"{field} must be true")

    output = contract.get("generation_output_contract")
    if not isinstance(output, dict) or output.get("count") != 1:
        raise ValueError("generation output count must be exactly 1")
    if output.get("approval_status_before_review") != "candidate":
        raise ValueError("generated art must remain candidate before review")
    if output.get("production_authorized_before_review") is not False:
        raise ValueError("generated art may not be production-authorized before review")
    if output.get("sha256_attestation_required_after_approval") is not True:
        raise ValueError("approved source SHA256 attestation must be required")


def validate_batch(batch: dict[str, Any]) -> None:
    if batch.get("schema") != BATCH_SCHEMA:
        raise ValueError("unsupported Vera generation batch schema")
    if batch.get("contract_id") != CONTRACT_ID:
        raise ValueError("batch is not bound to locked Vera contract")
    if batch.get("generation_mode") != "one_asset_per_request":
        raise ValueError("generation_mode must be one_asset_per_request")

    targets = batch.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("targets must be a non-empty list")

    ids: set[str] = set()
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError("each generation target must be an object")
        missing = REQUIRED_TARGET_FIELDS - set(target)
        if missing:
            raise ValueError(f"generation target missing fields: {sorted(missing)}")

        asset_id = target["asset_id"]
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError("asset_id must be a non-empty string")
        if asset_id in ids:
            raise ValueError(f"duplicate asset_id: {asset_id}")
        ids.add(asset_id)

        footprint_raw = target["footprint_tiles"]
        if not isinstance(footprint_raw, list) or len(footprint_raw) != 2:
            raise ValueError(f"{asset_id}: footprint_tiles must be [1,1] or [2,2]")
        footprint = tuple(footprint_raw)
        if footprint not in ALLOWED_FOOTPRINTS:
            raise ValueError(f"{asset_id}: unsupported footprint {footprint_raw}")
        if target["pixel_size"] != list(ALLOWED_FOOTPRINTS[footprint]):
            raise ValueError(f"{asset_id}: pixel_size does not match footprint")

        if target["original_plushbound_art_required"] is not True:
            raise ValueError(f"{asset_id}: original Plushbound artwork must be required")
        if not isinstance(target["top_down_required"], bool):
            raise ValueError(f"{asset_id}: top_down_required must be boolean")
        if not isinstance(target["tileable_required"], bool):
            raise ValueError(f"{asset_id}: tileable_required must be boolean")

        for field in ("required_elements", "forbidden_elements"):
            values = target[field]
            if not isinstance(values, list) or not values or not all(isinstance(v, str) and v.strip() for v in values):
                raise ValueError(f"{asset_id}: {field} must be a non-empty string list")

        joined = " ".join(
            [
                str(target.get("visual_function", "")),
                *target["required_elements"],
            ]
        ).lower()
        forbidden_hits = sorted(term for term in FORBIDDEN_COMPOSITION_TERMS if term in joined)
        if forbidden_hits:
            raise ValueError(f"{asset_id}: assortment/showcase language forbidden: {forbidden_hits}")


def validate_files(contract_path: Path, batch_path: Path) -> None:
    validate_contract(_load(contract_path))
    validate_batch(_load(batch_path))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    validate_files(args.contract, args.batch)
    print("VERA_GENERATION_CONTRACT=PASS")
