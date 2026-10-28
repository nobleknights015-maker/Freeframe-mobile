"""Paid launcher binding the corrected FLUX2 repair controller to its isolated gate."""
from __future__ import annotations

import json
from pathlib import Path

from modal_worker import world_asset_pipeline_v2_flux2_reference_batch as impl
from modal_worker.world_asset_pipeline_v2_planner import validate_receiver_contract

AUTH_PATH = Path("modal_worker/world_asset_pipeline_v2_flux2_reference_paid_authorization.json")
STATE_PATH = Path("modal_worker/world_asset_pipeline_v2_state.json")
FREEZE_PATH = Path("modal_worker/world_asset_pipeline_v2_freeze.json")
EXPECTED_PREFLIGHT_RUN_ID = 40789252831


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_isolated_authorization(region: str, requested_count: int) -> dict:
    auth = _load(AUTH_PATH)
    state = _load(STATE_PATH)
    freeze = _load(FREEZE_PATH)
    if auth.get("schema") != "plushbound.world_asset_pipeline_v2_flux2_reference_paid_authorization.v1":
        raise RuntimeError("isolated repair authorization schema mismatch")
    if auth.get("enabled") is not True or auth.get("region") != region:
        raise RuntimeError("isolated repair authorization is closed or bound elsewhere")
    if auth.get("one_region_only") is not True or auth.get("reference_aware_runner_required") is not True:
        raise RuntimeError("isolated repair scope guard drift")
    caps = [auth.get("provider_calls_allowed"), auth.get("gpu_calls_allowed"), auth.get("generation_calls_allowed")]
    if any(not isinstance(v, int) or isinstance(v, bool) for v in caps):
        raise RuntimeError("isolated repair call caps must be integers")
    if len(set(caps)) != 1 or caps[0] != requested_count or not 1 <= requested_count <= 8:
        raise RuntimeError("isolated repair call caps must exactly equal requested count")
    if auth.get("manual_visual_qa_required") is not True:
        raise RuntimeError("manual QA requirement missing")
    if auth.get("compile_authorized") is not False or auth.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("isolated repair authorization is too broad")
    if auth.get("required_source_art_provenance") != "vera-modal-generated":
        raise RuntimeError("isolated repair provenance drift")
    if auth.get("reference_sheet_pixels_used_as_runtime_art") is not False:
        raise RuntimeError("isolated repair permits reference pixels as runtime art")
    if int(auth.get("validated_reference_worker_preflight_run_id", 0)) != EXPECTED_PREFLIGHT_RUN_ID:
        raise RuntimeError("isolated repair authorization is not pinned to the dedicated worker preflight")
    if freeze.get("accepted_assets_immutable") is not True:
        raise RuntimeError("accepted asset immutability protection missing")
    if freeze.get("missing_local_artifact_is_not_rerender_authority") is not True:
        raise RuntimeError("missing-artifact rerender protection missing")
    if freeze.get("catalog_wide_launch_authorized") is not False or state.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("catalog-wide generation unexpectedly authorized")
    receiver = validate_receiver_contract(state_data=state, freeze_data=freeze)
    return {
        "status": "PASS_ISOLATED_FLUX2_REFERENCE_REPAIR_AUTHORIZATION",
        "region": region,
        "authorized_call_cap": requested_count,
        "receiver_contract_status": receiver["status"],
    }


def run(region: str, requested_ids: list[str]) -> dict:
    validate_isolated_authorization(region, len(requested_ids))
    # Bind the controller's internal authorization hook to this isolated gate.
    impl.validate_paid_authorization = validate_isolated_authorization
    return impl.run(region, requested_ids)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--request-ids-json", required=True)
    args = parser.parse_args()
    ids = json.loads(args.request_ids_json)
    result = run(args.region, ids)
    print(json.dumps({
        "status": result["status"],
        "region": result["region"],
        "requested_count": result["requested_count"],
        "machine_pass_count": result["machine_pass_count"],
        "machine_rejected_or_error_count": result["machine_rejected_or_error_count"],
        "total_gpu_seconds": result["total_gpu_seconds"],
        "source_art_provenance": result["source_art_provenance"],
        "reference_sheet_pixels_used_as_runtime_art": result["reference_sheet_pixels_used_as_runtime_art"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
