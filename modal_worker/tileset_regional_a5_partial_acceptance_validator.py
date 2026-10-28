"""Validate a manually accepted one-source A5 repair probe before remaining repair."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCOPE = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
REPAIR_POLICY = Path("modal_worker/tileset_regional_a5_repair_policy.json")
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


def load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing required evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate(path: Path, expected_region: str | None = None) -> dict:
    scope = load(SCOPE)
    policy = load(REPAIR_POLICY)
    qa = load(QA_CONTRACT)
    partial = load(path)

    if scope.get("schema") != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("regional A5 scope schema drift")
    if policy.get("schema") != "plushbound.tileset_regional_a5_repair_policy.v1":
        raise RuntimeError("regional A5 repair policy schema drift")
    if qa.get("schema") != "plushbound.tileset_regional_a5_visual_qa_contract.v1":
        raise RuntimeError("regional A5 visual QA schema drift")
    if partial.get("schema") != "plushbound.tileset_regional_a5_partial_acceptance.v1":
        raise RuntimeError("unexpected partial acceptance schema")
    if partial.get("status") != "PARTIAL_ACCEPTANCE_PROBE_GREEN_1_OF_8":
        raise RuntimeError("partial acceptance is not a green one-source probe")

    region = partial.get("region")
    if expected_region is not None and region != expected_region:
        raise RuntimeError("partial acceptance region mismatch")
    if region == "elyndor" or region not in scope.get("remaining_regions", []):
        raise RuntimeError("partial acceptance does not target an unfinished regional A5 scope")
    regional = scope["regions"][region]
    if partial.get("target_sheet_type") != "A5" or partial.get("stable_sheet_id") != regional.get("stable_sheet_id"):
        raise RuntimeError("partial acceptance target/stable sheet mismatch")
    if partial.get("prompt_contract_version") != policy.get("prompt_contract_version"):
        raise RuntimeError("partial acceptance prompt contract drift")
    if partial.get("qa_contract_schema") != qa["schema"]:
        raise RuntimeError("partial acceptance is not bound to the current visual QA contract")

    quarantine_path = Path(str(partial.get("source_quarantine_path", "")))
    quarantine = load(quarantine_path)
    if quarantine.get("schema") != "plushbound.tileset_regional_a5_source_quarantine.v1":
        raise RuntimeError("partial acceptance quarantine schema drift")
    if quarantine.get("region") != region or quarantine.get("accepted_source_count") != 0:
        raise RuntimeError("partial acceptance quarantine identity/accounting drift")
    failed_ids = set(quarantine["rerender_authority"]["failed_source_ids"])
    if len(failed_ids) != 8:
        raise RuntimeError("quarantine must contain exactly eight originally failed source IDs")

    if partial.get("accepted_source_count") != 1:
        raise RuntimeError("partial acceptance must contain exactly one accepted probe source")
    accepted = partial.get("accepted_sources", [])
    if len(accepted) != 1:
        raise RuntimeError("partial acceptance source record count must be exactly one")
    row = accepted[0]
    asset_id = row.get("asset_id")
    if asset_id not in failed_ids:
        raise RuntimeError("accepted probe source was not originally quarantined")
    if partial.get("accepted_source_ids") != [asset_id]:
        raise RuntimeError("accepted source ID list does not exactly match the probe record")
    if row.get("machine_status") != "PASS" or row.get("manual_visual_status") != "PASS":
        raise RuntimeError("probe source must pass machine and manual visual QA")
    if row.get("generation_attempts") != 1:
        raise RuntimeError("probe source generation attempts must remain exactly one")
    if row.get("source_size") != [384, 384] or row.get("normalized_size") != [48, 48]:
        raise RuntimeError("probe source geometry drift")
    for key in ("raw_sha256", "normalized_sha256"):
        value = row.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise RuntimeError(f"invalid probe {key}")
    checks = row.get("manual_checks")
    if not isinstance(checks, dict) or set(checks) != EXPECTED_SOURCE_CHECKS:
        raise RuntimeError("probe manual source check set does not match QA contract")
    if any(value != "PASS" for value in checks.values()):
        raise RuntimeError("probe has a failed manual source check")

    remaining = partial.get("remaining_failed_source_ids")
    expected_remaining = sorted(failed_ids - {asset_id})
    if sorted(remaining or []) != expected_remaining or len(expected_remaining) != 7:
        raise RuntimeError("remaining repair scope must be exactly the seven failed non-probe IDs")
    if partial.get("accepted_source_ids_protected_from_rerender") is not True:
        raise RuntimeError("accepted probe source is not protected from rerender")
    if partial.get("remaining_repair_authorized") is not True:
        raise RuntimeError("partial acceptance does not authorize the bounded remaining repair")
    if partial.get("compile_authorized") is not False or partial.get("deterministic_finalize_authorized") is not False:
        raise RuntimeError("partial acceptance incorrectly authorizes compile/finalize")
    if partial.get("catalog_wide_launch_authorized") is not False or partial.get("runtime_import_proof") is not False:
        raise RuntimeError("partial acceptance widened scope or claimed runtime import")

    return {
        "schema": "plushbound.tileset_regional_a5_partial_acceptance_validation.v1",
        "status": "PASS_PARTIAL_ACCEPTANCE_PROBE_GREEN_1_OF_8",
        "region": region,
        "stable_sheet_id": regional["stable_sheet_id"],
        "accepted_source_id": asset_id,
        "accepted_source_count": 1,
        "remaining_repair_source_count": 7,
        "accepted_source_ids_protected_from_rerender": True,
        "compile_authorized": False,
        "deterministic_finalize_authorized": False,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partial-acceptance", required=True, type=Path)
    parser.add_argument("--region")
    args = parser.parse_args()
    print(json.dumps(validate(args.partial_acceptance, args.region), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
