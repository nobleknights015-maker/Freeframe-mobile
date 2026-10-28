"""Bounded paid launcher for reference-aware World Asset Pipeline V2 generation.

This intentionally leaves historical state/freeze receipts untouched. A separate
one-shot authorization overlay must exactly match the requested region/count.
"""
from __future__ import annotations

import json
from pathlib import Path

from modal_worker.world_asset_pipeline_v2_planner import build_rows, validate_receiver_contract
from modal_worker.world_asset_pipeline_v2_reference_runner import _run, _save, declaration_validation

AUTH_PATH = Path("modal_worker/world_asset_pipeline_v2_paid_authorization.json")
FREEZE_PATH = Path("modal_worker/world_asset_pipeline_v2_freeze.json")
STATE_PATH = Path("modal_worker/world_asset_pipeline_v2_state.json")
MAX_BATCH_SIZE = 8


def _load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing V2 input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_reference_paid_authorization(region: str, requested_count: int) -> dict:
    auth = _load(AUTH_PATH)
    freeze = _load(FREEZE_PATH)
    state = _load(STATE_PATH)

    if auth.get("schema") != "plushbound.world_asset_pipeline_v2_paid_authorization.v1":
        raise RuntimeError("reference paid authorization schema mismatch")
    if auth.get("enabled") is not True:
        raise RuntimeError("reference paid authorization is disabled")
    if auth.get("region") != region:
        raise RuntimeError("reference paid authorization is bound to another region")
    if not isinstance(requested_count, int) or isinstance(requested_count, bool) or not 1 <= requested_count <= MAX_BATCH_SIZE:
        raise RuntimeError("requested_count must be between 1 and 8")

    limits = [
        auth.get("provider_calls_allowed"),
        auth.get("gpu_calls_allowed"),
        auth.get("generation_calls_allowed"),
    ]
    if any(not isinstance(v, int) or isinstance(v, bool) for v in limits):
        raise RuntimeError("reference paid authorization call caps must be integers")
    if len(set(limits)) != 1 or limits[0] != requested_count:
        raise RuntimeError("reference paid authorization caps must exactly equal requested_count")

    if auth.get("reference_aware_runner_required") is not True:
        raise RuntimeError("reference-aware runner is not required by authorization")
    if auth.get("required_source_art_provenance") != "vera-modal-generated":
        raise RuntimeError("authorization lost Vera/Modal provenance requirement")
    if auth.get("reference_sheet_pixels_used_as_runtime_art") is not False:
        raise RuntimeError("authorization permits reference-sheet runtime pixels")
    if auth.get("manual_visual_qa_required") is not True:
        raise RuntimeError("authorization must require manual visual QA")
    if auth.get("compile_authorized") is not False:
        raise RuntimeError("authorization must keep compile disabled")
    if auth.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("authorization must keep catalog-wide launch disabled")
    if int(auth.get("validated_reference_preflight_run_id", 0)) != 40786484554:
        raise RuntimeError("authorization is not pinned to the validated reference preflight")

    # Historical receipts remain frozen/read-only; only this narrow overlay opens calls.
    if freeze.get("accepted_assets_immutable") is not True:
        raise RuntimeError("accepted-asset immutability protection missing")
    if freeze.get("missing_local_artifact_is_not_rerender_authority") is not True:
        raise RuntimeError("missing-artifact rerender protection missing")
    if freeze.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("historical freeze unexpectedly permits catalog-wide launch")
    if state.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("historical state unexpectedly permits catalog-wide launch")
    receiver = validate_receiver_contract(state_data=state, freeze_data=freeze)

    declaration = declaration_validation()
    if declaration.get("status") != "PASS_ZERO_GPU_REFERENCE_AWARE_RUNNER_DECLARATION":
        raise RuntimeError("reference-aware runner declaration is not green")
    if declaration.get("reference_sheet_pixels_used_as_runtime_art") is not False:
        raise RuntimeError("runner permits reference-sheet runtime pixels")
    if declaration.get("required_source_art_provenance") != "vera-modal-generated":
        raise RuntimeError("runner provenance requirement drifted")

    return {
        "status": "PASS_REFERENCE_PAID_AUTHORIZATION",
        "region": region,
        "authorized_call_cap": requested_count,
        "manual_visual_qa_required": True,
        "compile_authorized": False,
        "catalog_wide_launch_authorized": False,
        "source_art_provenance": "vera-modal-generated",
        "reference_sheet_pixels_used_as_runtime_art": False,
        "receiver_contract_status": receiver["status"],
    }


def run(region: str, requested_ids: list[str]) -> dict:
    if not isinstance(requested_ids, list) or not 1 <= len(requested_ids) <= MAX_BATCH_SIZE:
        raise RuntimeError("requested_ids must contain 1..8 IDs")
    if len(requested_ids) != len(set(requested_ids)):
        raise RuntimeError("requested_ids contains duplicates")
    validate_reference_paid_authorization(region, len(requested_ids))
    rows, plan = build_rows(region, requested_ids)
    if [row["asset_id"] for row in rows] != requested_ids:
        raise RuntimeError("planner output does not exactly match requested IDs")
    if set(requested_ids).intersection(plan["accepted_ids_excluded"]):
        raise RuntimeError("requested IDs overlap accepted IDs")
    report = _run(region, rows, plan["accepted_ids_excluded"])
    return _save(report)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--request-ids-json", required=True)
    args = parser.parse_args()
    ids = json.loads(args.request_ids_json)
    clean = run(args.region, ids)
    print(json.dumps({
        "status": clean["status"],
        "region": clean["region"],
        "requested_count": clean["requested_count"],
        "machine_pass_count": clean["machine_pass_count"],
        "machine_rejected_or_error_count": clean["machine_rejected_or_error_count"],
        "total_gpu_seconds": clean["total_gpu_seconds"],
        "source_art_provenance": clean["source_art_provenance"],
        "reference_sheet_pixels_used_as_runtime_art": clean["reference_sheet_pixels_used_as_runtime_art"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
