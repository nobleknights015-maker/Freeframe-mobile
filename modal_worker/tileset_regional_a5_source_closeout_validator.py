"""Fail-closed validator for manually reviewed regional A5 source closeouts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCOPE = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
QA_CONTRACT = Path("modal_worker/tileset_regional_a5_visual_qa_contract.json")
EXPECTED_SOURCE_CHECKS = {
    "material_semantics",
    "surface_not_scene",
    "no_grid_or_contact_sheet",
    "no_text_or_symbols",
    "no_isolated_objects",
    "seam_friendly_distribution",
    "plushbound_material_language",
    "region_coherence",
}
EXPECTED_REGION_CHECKS = {
    "eight_distinct_families",
    "no_cross_region_identity_drift",
    "no_duplicate_source_master",
    "contact_sheet_coherence",
}


def _load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate(path: Path, expected_region: str | None = None) -> dict:
    scope = _load(SCOPE)
    qa = _load(QA_CONTRACT)
    closeout = _load(path)

    if scope.get("schema") != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("regional A5 scope schema drift")
    if qa.get("schema") != "plushbound.tileset_regional_a5_visual_qa_contract.v1":
        raise RuntimeError("regional A5 QA contract schema drift")
    if closeout.get("schema") != "plushbound.tileset_regional_a5_source_closeout.v1":
        raise RuntimeError("unexpected source closeout schema")
    if closeout.get("status") != "CLOSED_GREEN_8_OF_8":
        raise RuntimeError("source closeout is not green 8/8")

    region = closeout.get("region")
    if expected_region is not None and region != expected_region:
        raise RuntimeError("source closeout region does not match expected region")
    if region == "elyndor" or region not in scope.get("remaining_regions", []):
        raise RuntimeError("source closeout does not target an unfinished regional A5 scope")
    regional = scope["regions"][region]
    if closeout.get("target_sheet_type") != "A5":
        raise RuntimeError("source closeout target sheet is not A5")
    if closeout.get("stable_sheet_id") != regional.get("stable_sheet_id"):
        raise RuntimeError("source closeout stable sheet ID mismatch")
    if closeout.get("qa_contract_schema") != qa["schema"]:
        raise RuntimeError("source closeout does not bind the current manual QA contract")
    if closeout.get("machine_gate") != "PASS_8_OF_8":
        raise RuntimeError("source machine gate did not pass 8/8")
    if closeout.get("manual_visual_gate") != "PASS_8_OF_8":
        raise RuntimeError("source manual visual gate did not pass 8/8")
    if closeout.get("accepted_source_ids_protected_from_rerender") is not True:
        raise RuntimeError("accepted source IDs are not protected from rerender")
    if closeout.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("catalog-wide launch unexpectedly authorized")
    if closeout.get("runtime_import_proof") is not False:
        raise RuntimeError("source closeout incorrectly claims runtime import proof")
    if closeout.get("generation_retry_count") != 0:
        raise RuntimeError("source closeout indicates an unapproved generation retry")

    rows = closeout.get("sources", [])
    if len(rows) != 8 or len({row.get("asset_id") for row in rows}) != 8:
        raise RuntimeError("source closeout must contain exactly eight unique sources")
    expected_ids = {
        f"tileset.{region}.a5.source.{material}"
        for material in regional.get("materials", [])
    }
    if {row.get("asset_id") for row in rows} != expected_ids:
        raise RuntimeError("source closeout IDs do not match the locked regional material scope")

    raw_hashes = []
    normalized_hashes = []
    for row in rows:
        if row.get("manual_visual_status") != "PASS":
            raise RuntimeError(f"{row.get('asset_id')}: manual visual status is not PASS")
        checks = row.get("manual_checks")
        if not isinstance(checks, dict) or set(checks) != EXPECTED_SOURCE_CHECKS:
            raise RuntimeError(f"{row.get('asset_id')}: manual check set does not match QA contract")
        if any(value != "PASS" for value in checks.values()):
            raise RuntimeError(f"{row.get('asset_id')}: one or more manual source checks failed")
        raw_hash = row.get("raw_sha256")
        normalized_hash = row.get("normalized_sha256")
        if not isinstance(raw_hash, str) or len(raw_hash) != 64:
            raise RuntimeError(f"{row.get('asset_id')}: invalid raw SHA-256")
        if not isinstance(normalized_hash, str) or len(normalized_hash) != 64:
            raise RuntimeError(f"{row.get('asset_id')}: invalid normalized SHA-256")
        raw_hashes.append(raw_hash)
        normalized_hashes.append(normalized_hash)
        if row.get("generation_attempts") != 1:
            raise RuntimeError(f"{row.get('asset_id')}: generation attempt count must remain exactly one")
        if row.get("source_size") != [384, 384] or row.get("normalized_size") != [48, 48]:
            raise RuntimeError(f"{row.get('asset_id')}: source/normalized geometry drift")

    if len(set(raw_hashes)) != 8 or len(set(normalized_hashes)) != 8:
        raise RuntimeError("source closeout contains duplicate raw or normalized hashes")

    region_checks = closeout.get("region_manual_checks")
    if not isinstance(region_checks, dict) or set(region_checks) != EXPECTED_REGION_CHECKS:
        raise RuntimeError("region manual check set does not match QA contract")
    if any(value != "PASS" for value in region_checks.values()):
        raise RuntimeError("one or more region-level manual checks failed")

    return {
        "schema": "plushbound.tileset_regional_a5_source_closeout_validation.v1",
        "status": "PASS_CLOSED_GREEN_8_OF_8",
        "region": region,
        "stable_sheet_id": regional["stable_sheet_id"],
        "source_count": 8,
        "unique_raw_hashes": 8,
        "unique_normalized_hashes": 8,
        "manual_source_checks_per_asset": len(EXPECTED_SOURCE_CHECKS),
        "manual_region_checks": len(EXPECTED_REGION_CHECKS),
        "accepted_source_ids_protected_from_rerender": True,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--closeout", required=True, type=Path)
    parser.add_argument("--region")
    args = parser.parse_args()
    print(json.dumps(validate(args.closeout, args.region), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
