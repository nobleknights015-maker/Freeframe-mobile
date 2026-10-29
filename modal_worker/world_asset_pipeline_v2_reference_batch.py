"""Compatibility adapter from the legacy reference executor to the corrected FLUX2 repair lane.

The GitHub Actions executor remains static. Tideglass correction runs bind the exact
material-specific reference anchor at runtime, compute its SHA from committed bytes,
and restore the regional conditioning file after the bounded FLUX2 call.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from modal_worker.world_asset_pipeline_v2_flux2_reference_batch import (
    run as _flux2_run,
    validate_paid_authorization as _flux2_validate_paid_authorization,
)

CONDITIONING_PATH = Path("modal_worker/world_asset_pipeline_v2_reference_conditioning.json")
TIDEGLASS_PREFIX = "tileset.tideglass-coast.a5.source."
TIDEGLASS_CORRECTION_REFS = {
    "dry_sand": "ec305b5631fb47bc7c26af7d91d2b24e8a03e9ba399de22fc53b90a6e1c64566",
    "coastal_stone": "d9c6eabf672b139714e62832cc3b8588ac81f304b9f6c3bbd324c36daa11bfed",
    "cliff_stone": "259112611c057ad4b3d63d7035ff25f09fdb855a1a555497d2d1194c38d07fbf",
    "saltworn_board": "dde50ac08e4607337b7912018c9b2bbdf586dbac87db7546b80c1b4d35519f67",
    "tidal_silt": "b27ea85f7eab39840e7ccc2ce9dc5bfa2b77989d391368fb0c1f04a84fbf76e8",
}


def validate_reference_paid_authorization(region: str, requested_count: int) -> dict:
    gate = _flux2_validate_paid_authorization(region, requested_count)
    return {
        "status": "PASS_REFERENCE_PAID_AUTHORIZATION",
        "region": region,
        "authorized_call_cap": requested_count,
        "manual_visual_qa_required": True,
        "compile_authorized": False,
        "catalog_wide_launch_authorized": False,
        "source_art_provenance": "vera-modal-generated",
        "reference_sheet_pixels_used_as_runtime_art": False,
        "receiver_contract_status": gate["receiver_contract_status"],
        "renderer_lane": "flux2_klein_reference_v2",
    }


def _bind_tideglass_correction(region: str, requested_ids: list[str]) -> str | None:
    if region != "tideglass-coast":
        return None
    if len(requested_ids) != 1 or not requested_ids[0].startswith(TIDEGLASS_PREFIX):
        raise RuntimeError("Tideglass correction adapter requires exactly one scoped source ID")
    material = requested_ids[0][len(TIDEGLASS_PREFIX):]
    sheet_sha = TIDEGLASS_CORRECTION_REFS.get(material)
    if sheet_sha is None:
        raise RuntimeError(f"{material}: no accepted correction reference is registered")
    anchor = Path(f"modal_worker/project_references/tideglass_correction_round/{material}_reference_anchor_256.jpg")
    if not anchor.is_file():
        raise RuntimeError(f"{material}: committed correction anchor is missing")
    anchor_sha = hashlib.sha256(anchor.read_bytes()).hexdigest()
    if anchor_sha == sheet_sha:
        raise RuntimeError(f"{material}: correction anchor must not be the original reference-sheet bytes")

    original = CONDITIONING_PATH.read_text(encoding="utf-8")
    cfg = json.loads(original)
    reg = cfg["regions"][region]
    reg["anchor_path"] = str(anchor)
    reg["anchor_sha256"] = anchor_sha
    reg["reference_role"] = "material_specific_correction_visual_authority_only"
    reg["source_reference_hashes"] = {
        "correction_material": material,
        "correction_reference_sheet_sha256": sheet_sha,
        "correction_anchor_sha256": anchor_sha,
    }
    CONDITIONING_PATH.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return original


def run(region: str, requested_ids: list[str]) -> dict:
    validate_reference_paid_authorization(region, len(requested_ids))
    original = _bind_tideglass_correction(region, requested_ids)
    try:
        return _flux2_run(region, requested_ids)
    finally:
        if original is not None:
            CONDITIONING_PATH.write_text(original, encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--request-ids-json", required=True)
    args = parser.parse_args()
    requested_ids = json.loads(args.request_ids_json)
    clean = run(args.region, requested_ids)
    print(json.dumps({
        "status": clean["status"],
        "region": clean["region"],
        "requested_count": clean["requested_count"],
        "machine_pass_count": clean["machine_pass_count"],
        "machine_rejected_or_error_count": clean["machine_rejected_or_error_count"],
        "total_gpu_seconds": clean["total_gpu_seconds"],
        "source_art_provenance": clean["source_art_provenance"],
        "reference_sheet_pixels_used_as_runtime_art": clean["reference_sheet_pixels_used_as_runtime_art"],
        "renderer_lane": "flux2_klein_reference_v2",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
