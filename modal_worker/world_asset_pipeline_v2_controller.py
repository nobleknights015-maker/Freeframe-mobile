"""World Asset Pipeline V2 state controller.

This module replaces workflow-specific repair state with one authoritative model:
asset IDs are PENDING, ACCEPTED, REJECTED_SEMANTIC, or REJECTED_TECHNICAL.
Accepted assets come only from hash-bound regional closeouts and are never eligible
for generation again. The controller itself never calls a provider or GPU.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FREEZE_PATH = Path("modal_worker/world_asset_pipeline_v2_freeze.json")
STATE_PATH = Path("modal_worker/world_asset_pipeline_v2_state.json")
DEFAULT_SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
ALLOWED_ASSET_STATES = {"PENDING", "ACCEPTED", "REJECTED_SEMANTIC", "REJECTED_TECHNICAL"}
ELIGIBLE_GENERATION_STATES = {"PENDING", "REJECTED_SEMANTIC", "REJECTED_TECHNICAL"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing required V2 evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_ids(region: str, regional: dict) -> list[str]:
    materials = list(regional.get("materials", []))
    if len(materials) != 8 or len(set(materials)) != 8:
        raise RuntimeError(f"{region}: V2 requires exactly eight unique regional material keys")
    return [f"tileset.{region}.a5.source.{material}" for material in materials]


def _validate_freeze(freeze: dict) -> None:
    if freeze.get("schema") != "plushbound.world_asset_pipeline_v2_freeze.v1":
        raise RuntimeError("unexpected V2 freeze schema")
    if freeze.get("production_frozen") is not True:
        raise RuntimeError("V2 rebuild requires production_frozen=true")
    if freeze.get("paid_remote_execution_allowed") is not False:
        raise RuntimeError("V2 rebuild freeze unexpectedly allows paid execution")
    if [freeze.get("provider_calls_allowed"), freeze.get("gpu_calls_allowed"), freeze.get("generation_calls_allowed")] != [0, 0, 0]:
        raise RuntimeError("V2 rebuild freeze must authorize zero provider/GPU/generation calls")
    if freeze.get("accepted_assets_immutable") is not True:
        raise RuntimeError("accepted asset immutability lock is missing")
    if freeze.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("catalog-wide production must remain disabled")


def _validate_state(state: dict) -> None:
    if state.get("schema") != "plushbound.world_asset_pipeline_v2_state.v1":
        raise RuntimeError("unexpected V2 state schema")
    if state.get("pipeline_version") != 2:
        raise RuntimeError("unexpected V2 state version")
    if state.get("production_frozen") is not True or state.get("paid_execution_enabled") is not False:
        raise RuntimeError("V2 rebuild state is not frozen")
    if state.get("active_paid_region") is not None:
        raise RuntimeError("V2 rebuild cannot have an active paid region")
    if state.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("catalog-wide production must remain disabled")
    if set(state.get("allowed_asset_states", [])) != ALLOWED_ASSET_STATES:
        raise RuntimeError("V2 asset-state vocabulary drifted")


def _accepted_from_closeout(region: str, closeout_path: Path, expected_ids: set[str]) -> dict[str, dict]:
    closeout = _load(closeout_path)
    if closeout.get("schema") != "plushbound.tileset_regional_a5_source_closeout.v1":
        raise RuntimeError(f"{region}: unexpected source closeout schema")
    if closeout.get("region") != region or closeout.get("stable_sheet_id") != f"tileset.{region}.a5":
        raise RuntimeError(f"{region}: source closeout identity mismatch")
    if closeout.get("status") != "CLOSED_GREEN_8_OF_8":
        raise RuntimeError(f"{region}: source closeout is not green 8/8")
    if closeout.get("machine_gate") != "PASS_8_OF_8" or closeout.get("manual_visual_gate") != "PASS_8_OF_8":
        raise RuntimeError(f"{region}: source closeout did not pass both machine and manual gates")
    if closeout.get("accepted_source_ids_protected_from_rerender") is not True:
        raise RuntimeError(f"{region}: accepted source protection is missing")
    rows = list(closeout.get("sources", []))
    if len(rows) != 8:
        raise RuntimeError(f"{region}: source closeout must contain exactly eight source rows")
    accepted: dict[str, dict] = {}
    for row in rows:
        asset_id = str(row.get("asset_id", ""))
        raw_sha = str(row.get("raw_sha256", ""))
        normalized_sha = str(row.get("normalized_sha256", ""))
        if asset_id in accepted:
            raise RuntimeError(f"{region}: duplicate accepted source ID {asset_id}")
        if asset_id not in expected_ids:
            raise RuntimeError(f"{region}: closeout contains out-of-scope asset {asset_id}")
        if not SHA256_RE.match(raw_sha) or not SHA256_RE.match(normalized_sha):
            raise RuntimeError(f"{asset_id}: invalid accepted SHA256 evidence")
        accepted[asset_id] = {
            "state": "ACCEPTED",
            "raw_sha256": raw_sha,
            "normalized_sha256": normalized_sha,
            "provenance": str(closeout_path),
            "machine_status": row.get("machine_status"),
            "manual_visual_status": row.get("manual_visual_status"),
        }
    if set(accepted) != expected_ids:
        missing = sorted(expected_ids - set(accepted))
        extra = sorted(set(accepted) - expected_ids)
        raise RuntimeError(f"{region}: closeout ID mismatch missing={missing} extra={extra}")
    return accepted


def resolve_state() -> dict:
    freeze = _load(FREEZE_PATH)
    state = _load(STATE_PATH)
    _validate_freeze(freeze)
    _validate_state(state)

    scope_path = Path(state.get("scope_manifest") or DEFAULT_SCOPE_PATH)
    scope = _load(scope_path)
    if scope.get("schema") != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("unexpected regional A5 scope schema")
    if scope.get("spend_gate", {}).get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("legacy scope unexpectedly authorizes catalog-wide production")

    closeouts = dict(state.get("accepted_region_source_closeouts", {}))
    overrides = dict(state.get("asset_state_overrides", {}))
    resolved_regions: dict[str, dict] = {}
    all_asset_ids: set[str] = set()

    for region in scope.get("remaining_regions", []):
        regional = scope.get("regions", {}).get(region)
        if not regional:
            raise RuntimeError(f"scope missing region definition: {region}")
        if regional.get("stable_sheet_id") != f"tileset.{region}.a5":
            raise RuntimeError(f"{region}: stable sheet ID drift")
        expected = _expected_ids(region, regional)
        expected_set = set(expected)
        if all_asset_ids.intersection(expected_set):
            raise RuntimeError(f"{region}: duplicate stable source ID across regions")
        all_asset_ids.update(expected_set)

        accepted: dict[str, dict] = {}
        if region in closeouts:
            accepted = _accepted_from_closeout(region, Path(closeouts[region]), expected_set)

        assets: dict[str, dict] = {}
        for asset_id in expected:
            if asset_id in accepted:
                assets[asset_id] = accepted[asset_id]
                continue
            override = overrides.get(asset_id, "PENDING")
            if isinstance(override, str):
                override_state = override
                reason = None
            elif isinstance(override, dict):
                override_state = override.get("state")
                reason = override.get("reason")
            else:
                raise RuntimeError(f"{asset_id}: invalid V2 state override")
            if override_state not in ALLOWED_ASSET_STATES:
                raise RuntimeError(f"{asset_id}: invalid V2 asset state {override_state}")
            if override_state == "ACCEPTED":
                raise RuntimeError(f"{asset_id}: ACCEPTED may only come from a hash-bound closeout")
            assets[asset_id] = {"state": override_state, "reason": reason}

        counts = {name: sum(1 for row in assets.values() if row["state"] == name) for name in sorted(ALLOWED_ASSET_STATES)}
        eligible = [asset_id for asset_id in expected if assets[asset_id]["state"] in ELIGIBLE_GENERATION_STATES]
        accepted_ids = [asset_id for asset_id in expected if assets[asset_id]["state"] == "ACCEPTED"]
        resolved_regions[region] = {
            "stable_sheet_id": regional["stable_sheet_id"],
            "region_state": state.get("region_overrides", {}).get(region, "PENDING"),
            "asset_count": 8,
            "state_counts": counts,
            "accepted_source_ids": accepted_ids,
            "eligible_generation_ids": eligible,
            "compile_eligible": len(accepted_ids) == 8,
            "assets": assets,
        }

    closed = dict(state.get("closed_region_sheets", {}))
    for region, row in closed.items():
        sha = str(row.get("sheet_sha256", ""))
        if not SHA256_RE.match(sha):
            raise RuntimeError(f"{region}: invalid closed sheet hash")
        if row.get("runtime_import_proof") is not False:
            raise RuntimeError(f"{region}: V2 may not infer live runtime import proof")

    return {
        "schema": "plushbound.world_asset_pipeline_v2_resolved_state.v1",
        "status": "PASS_ZERO_GPU_STATE_RESOLUTION",
        "production_frozen": True,
        "paid_execution_enabled": False,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
        "closed_region_sheets": closed,
        "regions": resolved_regions,
    }


def plan_region(region: str, requested_ids: list[str] | None = None) -> dict:
    resolved = resolve_state()
    if region in resolved["closed_region_sheets"]:
        raise RuntimeError(f"{region}: region is already closed/banked")
    regional = resolved["regions"].get(region)
    if not regional:
        raise RuntimeError(f"unknown V2 regional scope: {region}")
    eligible = list(regional["eligible_generation_ids"])
    if requested_ids is None:
        selected = eligible
    else:
        if len(requested_ids) != len(set(requested_ids)):
            raise RuntimeError("requested V2 asset IDs contain duplicates")
        refused = sorted(set(requested_ids) - set(eligible))
        if refused:
            raise RuntimeError(f"requested IDs are accepted or out of scope and are refused: {refused}")
        selected = [asset_id for asset_id in eligible if asset_id in set(requested_ids)]
    if len(selected) > 8:
        raise RuntimeError("V2 region plan exceeded the eight-source region cap")
    return {
        "schema": "plushbound.world_asset_pipeline_v2_region_plan.v1",
        "region": region,
        "stable_sheet_id": regional["stable_sheet_id"],
        "accepted_source_count": len(regional["accepted_source_ids"]),
        "selected_generation_count": len(selected),
        "selected_generation_ids": selected,
        "accepted_ids_excluded": regional["accepted_source_ids"],
        "compile_eligible": regional["compile_eligible"],
        "production_frozen": True,
        "paid_execution_authorized": False,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "manual_visual_qa_required": True,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
    }


def self_test() -> dict:
    resolved = resolve_state()
    if "gloamfen" not in resolved["regions"] or "silkspire" not in resolved["regions"]:
        raise RuntimeError("V2 self-test requires Gloamfen and Silkspire scopes")
    gloamfen = plan_region("gloamfen")
    silkspire = plan_region("silkspire")
    if gloamfen["accepted_source_count"] != 8 or gloamfen["selected_generation_count"] != 0 or not gloamfen["compile_eligible"]:
        raise RuntimeError("V2 failed to protect the accepted Gloamfen 8/8 source bank")
    if silkspire["accepted_source_count"] != 0 or silkspire["selected_generation_count"] != 8 or silkspire["compile_eligible"]:
        raise RuntimeError("V2 failed to derive fresh Silkspire source scope")
    if any([gloamfen["provider_calls"], gloamfen["gpu_calls"], gloamfen["generation_calls"], silkspire["provider_calls"], silkspire["gpu_calls"], silkspire["generation_calls"]]):
        raise RuntimeError("V2 controller self-test attempted paid/generation work")
    return {
        "schema": "plushbound.world_asset_pipeline_v2_self_test.v1",
        "status": "PASS_ZERO_GPU_V2_STATE_AND_PLANNING",
        "gloamfen_accepted": gloamfen["accepted_source_count"],
        "gloamfen_generation_selected": gloamfen["selected_generation_count"],
        "gloamfen_compile_eligible": gloamfen["compile_eligible"],
        "silkspire_accepted": silkspire["accepted_source_count"],
        "silkspire_generation_selected": silkspire["selected_generation_count"],
        "silkspire_compile_eligible": silkspire["compile_eligible"],
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "production_frozen": True,
        "runtime_import_proof": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolve", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--plan-region")
    parser.add_argument("--request-id", action="append", default=[])
    args = parser.parse_args()
    modes = sum(bool(x) for x in [args.resolve, args.self_test, args.plan_region])
    if modes != 1:
        parser.error("choose exactly one of --resolve, --self-test, or --plan-region")
    if args.self_test:
        result = self_test()
    elif args.resolve:
        result = resolve_state()
    else:
        result = plan_region(args.plan_region, args.request_id or None)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
