"""Compatibility adapter from the legacy reference executor to the corrected FLUX2 repair lane."""
from __future__ import annotations

import json

from modal_worker.world_asset_pipeline_v2_flux2_reference_batch import (
    run as _flux2_run,
    validate_paid_authorization as _flux2_validate_paid_authorization,
)


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


def run(region: str, requested_ids: list[str]) -> dict:
    validate_reference_paid_authorization(region, len(requested_ids))
    return _flux2_run(region, requested_ids)


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
