"""World Asset Pipeline V2 authoritative state controller.

One state model replaces probe/repair/final-repair workflow state. Every stable source
ID is PENDING, ACCEPTED, REJECTED_SEMANTIC, or REJECTED_TECHNICAL. ACCEPTED status
must be backed by immutable SHA256 evidence, either an individual asset acceptance
record or a completed regional 8/8 closeout. Accepted IDs are never generation-eligible.

State resolution is deliberately independent from the paid/frozen execution mode. The
controller must be able to answer "what is accepted/pending?" both while production is
frozen and while one bounded live region is authorized. Freeze enforcement belongs to
the execution gate, not to asset truth.

This module is deterministic and makes zero provider/GPU/generation calls.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FREEZE_PATH = Path("modal_worker/world_asset_pipeline_v2_freeze.json")
STATE_PATH = Path("modal_worker/world_asset_pipeline_v2_state.json")
ALLOWED_ASSET_STATES = {"PENDING", "ACCEPTED", "REJECTED_SEMANTIC", "REJECTED_TECHNICAL"}
ELIGIBLE_STATES = ALLOWED_ASSET_STATES - {"ACCEPTED"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_LIVE_BATCH_SIZE = 8


def _load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing required V2 evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_sha(value: object) -> bool:
    return bool(SHA256_RE.match(str(value or "")))


def _validate_freeze_contract(freeze: dict) -> None:
    """Validate invariant safety fields without requiring a particular execution mode."""
    if freeze.get("schema") != "plushbound.world_asset_pipeline_v2_freeze.v1":
        raise RuntimeError("unexpected V2 freeze schema")
    if freeze.get("accepted_assets_immutable") is not True:
        raise RuntimeError("V2 accepted-asset immutability lock drifted")
    if freeze.get("missing_local_artifact_is_not_rerender_authority") is not True:
        raise RuntimeError("V2 missing-artifact rerender protection drifted")
    if freeze.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("V2 catalog-wide generation must remain disabled")
    if freeze.get("runtime_import_proof") is not True:
        raise RuntimeError("V2 freeze contract lost the banked receiver proof")

    frozen = freeze.get("production_frozen")
    paid = freeze.get("paid_remote_execution_allowed")
    limits = [
        freeze.get("provider_calls_allowed"),
        freeze.get("gpu_calls_allowed"),
        freeze.get("generation_calls_allowed"),
    ]
    if frozen is True:
        if paid is not False or limits != [0, 0, 0]:
            raise RuntimeError("V2 frozen gate must authorize zero paid execution")
    elif frozen is False:
        if paid is not True:
            raise RuntimeError("V2 live gate must explicitly authorize paid execution")
        valid_limits = all(
            isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= MAX_LIVE_BATCH_SIZE
            for v in limits
        )
        if not valid_limits or len(set(limits)) != 1:
            raise RuntimeError("V2 live gate must use equal provider/GPU/generation caps between 1 and 8")
    else:
        raise RuntimeError("V2 freeze contract has invalid production_frozen state")


def _validate_state_contract(state: dict) -> None:
    """Validate state invariants without assuming frozen or live mode."""
    if state.get("schema") != "plushbound.world_asset_pipeline_v2_state.v1" or state.get("pipeline_version") != 2:
        raise RuntimeError("unexpected V2 state contract")
    if state.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("V2 state unexpectedly authorizes catalog-wide production")
    if state.get("runtime_import_proof") is not True:
        raise RuntimeError("V2 state lost the banked receiver proof")
    if set(state.get("allowed_asset_states", [])) != ALLOWED_ASSET_STATES:
        raise RuntimeError("V2 asset-state vocabulary drifted")

    frozen = state.get("production_frozen")
    paid = state.get("paid_execution_enabled")
    active = state.get("active_paid_region")
    if frozen is True:
        if paid is not False or active is not None:
            raise RuntimeError("V2 frozen state unexpectedly authorizes production")
    elif frozen is False:
        if paid is not True or not isinstance(active, str) or not active:
            raise RuntimeError("V2 live state must bind paid execution to exactly one region")
    else:
        raise RuntimeError("V2 state has invalid production_frozen value")


def _validate_mode_alignment(freeze: dict, state: dict) -> None:
    if freeze.get("production_frozen") != state.get("production_frozen"):
        raise RuntimeError("V2 freeze/state production mode mismatch")
    if freeze.get("production_frozen") is True:
        if state.get("paid_execution_enabled") is not False:
            raise RuntimeError("V2 frozen state/gate mismatch")
    else:
        if state.get("paid_execution_enabled") is not True:
            raise RuntimeError("V2 live state/gate mismatch")


def _require_frozen_mode(freeze: dict, state: dict) -> None:
    if freeze.get("production_frozen") is not True or freeze.get("paid_remote_execution_allowed") is not False:
        raise RuntimeError("V2 frozen-mode validation expected a closed paid gate")
    if state.get("production_frozen") is not True or state.get("paid_execution_enabled") is not False:
        raise RuntimeError("V2 frozen-mode validation expected frozen state")
    if state.get("active_paid_region") is not None:
        raise RuntimeError("V2 frozen-mode validation expected no active paid region")


def _expected(region: str, regional: dict) -> list[tuple[str, str]]:
    materials = list(regional.get("materials", []))
    if len(materials) != 8 or len(set(materials)) != 8:
        raise RuntimeError(f"{region}: expected exactly eight unique material keys")
    return [(material, f"tileset.{region}.a5.source.{material}") for material in materials]


def _accepted_from_region_closeout(region: str, path: Path, expected_ids: set[str]) -> dict[str, dict]:
    row = _load(path)
    if row.get("schema") != "plushbound.tileset_regional_a5_source_closeout.v1":
        raise RuntimeError(f"{region}: unexpected source closeout schema")
    if row.get("region") != region or row.get("stable_sheet_id") != f"tileset.{region}.a5":
        raise RuntimeError(f"{region}: source closeout identity mismatch")
    if row.get("status") != "CLOSED_GREEN_8_OF_8" or row.get("machine_gate") != "PASS_8_OF_8" or row.get("manual_visual_gate") != "PASS_8_OF_8":
        raise RuntimeError(f"{region}: source closeout is not machine+manual green 8/8")
    if row.get("accepted_source_ids_protected_from_rerender") is not True:
        raise RuntimeError(f"{region}: closeout does not protect accepted IDs")
    accepted: dict[str, dict] = {}
    for source in row.get("sources", []):
        asset_id = str(source.get("asset_id", ""))
        if asset_id in accepted or asset_id not in expected_ids:
            raise RuntimeError(f"{region}: invalid/duplicate closeout asset ID {asset_id}")
        if not _valid_sha(source.get("raw_sha256")) or not _valid_sha(source.get("normalized_sha256")):
            raise RuntimeError(f"{asset_id}: invalid accepted hashes")
        accepted[asset_id] = {
            "state": "ACCEPTED",
            "raw_sha256": source["raw_sha256"],
            "normalized_sha256": source["normalized_sha256"],
            "provenance_type": "REGION_CLOSEOUT",
            "provenance": str(path),
        }
    if set(accepted) != expected_ids:
        raise RuntimeError(f"{region}: closeout does not contain exact regional 8/8 IDs")
    return accepted


def _accepted_from_asset_record(asset_id: str, path: Path) -> dict:
    row = _load(path)
    if row.get("schema") != "plushbound.world_asset_pipeline_v2_asset_acceptance.v1":
        raise RuntimeError(f"{asset_id}: unexpected per-asset acceptance schema")
    if row.get("status") != "ACCEPTED" or row.get("asset_id") != asset_id:
        raise RuntimeError(f"{asset_id}: per-asset acceptance identity/status mismatch")
    if row.get("machine_gate") != "PASS" or row.get("manual_visual_gate") != "PASS":
        raise RuntimeError(f"{asset_id}: per-asset acceptance is not machine+manual green")
    if row.get("immutable") is not True or row.get("rerender_allowed") is not False:
        raise RuntimeError(f"{asset_id}: per-asset immutability lock missing")
    if not _valid_sha(row.get("raw_sha256")) or not _valid_sha(row.get("normalized_sha256")):
        raise RuntimeError(f"{asset_id}: invalid per-asset hashes")
    return {
        "state": "ACCEPTED",
        "raw_sha256": row["raw_sha256"],
        "normalized_sha256": row["normalized_sha256"],
        "provenance_type": "ASSET_ACCEPTANCE",
        "provenance": str(path),
    }


def resolve_state(*, require_frozen: bool = False) -> dict:
    freeze = _load(FREEZE_PATH)
    state = _load(STATE_PATH)
    _validate_freeze_contract(freeze)
    _validate_state_contract(state)
    _validate_mode_alignment(freeze, state)
    if require_frozen:
        _require_frozen_mode(freeze, state)

    scope = _load(Path(state["scope_manifest"]))
    if scope.get("schema") != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("unexpected regional A5 scope schema")
    if scope.get("spend_gate", {}).get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("legacy scope unexpectedly authorizes catalog-wide production")

    closeouts = dict(state.get("accepted_region_source_closeouts", {}))
    records = dict(state.get("accepted_asset_records", {}))
    overrides = dict(state.get("asset_state_overrides", {}))
    resolved_regions: dict[str, dict] = {}
    global_ids: set[str] = set()

    for region in scope.get("remaining_regions", []):
        regional = scope.get("regions", {}).get(region)
        if not regional or regional.get("stable_sheet_id") != f"tileset.{region}.a5":
            raise RuntimeError(f"{region}: missing/drifted regional scope")
        pairs = _expected(region, regional)
        expected_ids = {asset_id for _, asset_id in pairs}
        if global_ids.intersection(expected_ids):
            raise RuntimeError(f"{region}: stable source IDs collide with another region")
        global_ids.update(expected_ids)

        accepted: dict[str, dict] = {}
        if region in closeouts:
            accepted.update(_accepted_from_region_closeout(region, Path(closeouts[region]), expected_ids))
        for asset_id in expected_ids:
            if asset_id not in records:
                continue
            individual = _accepted_from_asset_record(asset_id, Path(records[asset_id]))
            if asset_id in accepted:
                existing = accepted[asset_id]
                if existing["raw_sha256"] != individual["raw_sha256"] or existing["normalized_sha256"] != individual["normalized_sha256"]:
                    raise RuntimeError(f"{asset_id}: region and per-asset acceptance hashes disagree")
            else:
                accepted[asset_id] = individual

        assets: dict[str, dict] = {}
        for material, asset_id in pairs:
            if asset_id in accepted:
                assets[asset_id] = {"material_key": material, **accepted[asset_id]}
                continue
            override = overrides.get(asset_id, "PENDING")
            if isinstance(override, str):
                asset_state, reason, prompt_suffix = override, None, None
            elif isinstance(override, dict):
                asset_state = override.get("state")
                reason = override.get("reason")
                prompt_suffix = override.get("prompt_suffix")
            else:
                raise RuntimeError(f"{asset_id}: invalid state override")
            if asset_state not in ALLOWED_ASSET_STATES or asset_state == "ACCEPTED":
                raise RuntimeError(f"{asset_id}: ACCEPTED requires hash-bound acceptance evidence")
            assets[asset_id] = {
                "material_key": material,
                "state": asset_state,
                "reason": reason,
                "prompt_suffix": prompt_suffix,
            }

        accepted_ids = [asset_id for _, asset_id in pairs if assets[asset_id]["state"] == "ACCEPTED"]
        eligible_ids = [asset_id for _, asset_id in pairs if assets[asset_id]["state"] in ELIGIBLE_STATES]
        counts = {name: sum(1 for item in assets.values() if item["state"] == name) for name in sorted(ALLOWED_ASSET_STATES)}
        resolved_regions[region] = {
            "stable_sheet_id": regional["stable_sheet_id"],
            "region_state": state.get("region_overrides", {}).get(region, "PENDING"),
            "asset_count": 8,
            "state_counts": counts,
            "accepted_source_ids": accepted_ids,
            "eligible_generation_ids": eligible_ids,
            "compile_eligible": len(accepted_ids) == 8,
            "assets": assets,
        }

    closed = dict(state.get("closed_region_sheets", {}))
    for region, row in closed.items():
        if not _valid_sha(row.get("sheet_sha256")):
            raise RuntimeError(f"{region}: invalid closed-sheet hash evidence")
        if not isinstance(row.get("runtime_import_proof"), bool):
            raise RuntimeError(f"{region}: closed-sheet runtime proof must be boolean")

    production_frozen = bool(state["production_frozen"])
    paid_execution_enabled = bool(state["paid_execution_enabled"])
    return {
        "schema": "plushbound.world_asset_pipeline_v2_resolved_state.v1",
        "status": "PASS_ZERO_GPU_STATE_RESOLUTION",
        "production_frozen": production_frozen,
        "paid_execution_enabled": paid_execution_enabled,
        "active_paid_region": state.get("active_paid_region"),
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": True,
        "closed_region_sheets": closed,
        "regions": resolved_regions,
    }


def plan_region(region: str, requested_ids: list[str] | None = None) -> dict:
    resolved = resolve_state()
    if region in resolved["closed_region_sheets"]:
        raise RuntimeError(f"{region}: region already closed/banked")
    regional = resolved["regions"].get(region)
    if not regional:
        raise RuntimeError(f"unknown V2 region: {region}")
    eligible = list(regional["eligible_generation_ids"])
    if requested_ids is None:
        selected = eligible
    else:
        if len(requested_ids) != len(set(requested_ids)):
            raise RuntimeError("duplicate requested V2 asset IDs")
        refused = sorted(set(requested_ids) - set(eligible))
        if refused:
            raise RuntimeError(f"accepted/out-of-scope IDs refused: {refused}")
        requested = set(requested_ids)
        selected = [asset_id for asset_id in eligible if asset_id in requested]
    if len(selected) > 8:
        raise RuntimeError("V2 selected more than one region's eight-source cap")
    live_for_region = resolved["paid_execution_enabled"] and resolved.get("active_paid_region") == region
    return {
        "schema": "plushbound.world_asset_pipeline_v2_region_plan.v1",
        "region": region,
        "stable_sheet_id": regional["stable_sheet_id"],
        "accepted_source_count": len(regional["accepted_source_ids"]),
        "selected_generation_count": len(selected),
        "selected_generation_ids": selected,
        "accepted_ids_excluded": regional["accepted_source_ids"],
        "compile_eligible": regional["compile_eligible"],
        "production_frozen": resolved["production_frozen"],
        "paid_execution_authorized": bool(live_for_region),
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "manual_visual_qa_required": True,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": True,
    }


def self_test() -> dict:
    resolved = resolve_state(require_frozen=True)
    gloamfen = plan_region("gloamfen")
    silkspire = plan_region("silkspire")
    if gloamfen["accepted_source_count"] != 8 or gloamfen["selected_generation_count"] != 0 or not gloamfen["compile_eligible"]:
        raise RuntimeError("V2 failed to protect Gloamfen accepted 8/8")
    silkspire_total = silkspire["accepted_source_count"] + silkspire["selected_generation_count"]
    if silkspire_total != 8:
        raise RuntimeError("V2 Silkspire accounting no longer resolves to exact regional 8/8")
    if set(silkspire["accepted_ids_excluded"]).intersection(silkspire["selected_generation_ids"]):
        raise RuntimeError("V2 Silkspire plan overlaps accepted and generation-eligible IDs")
    if silkspire["compile_eligible"] != (silkspire["accepted_source_count"] == 8):
        raise RuntimeError("V2 Silkspire compile eligibility disagrees with accepted-source count")
    accepted_probe = gloamfen["accepted_ids_excluded"][0]
    try:
        plan_region("gloamfen", [accepted_probe])
    except RuntimeError:
        accepted_refusal_pass = True
    else:
        accepted_refusal_pass = False
    if not accepted_refusal_pass:
        raise RuntimeError("V2 did not refuse an accepted asset ID")
    return {
        "schema": "plushbound.world_asset_pipeline_v2_self_test.v1",
        "status": "PASS_ZERO_GPU_V2_STATE_AND_PLANNING",
        "resolved_region_count": len(resolved["regions"]),
        "gloamfen_accepted": 8,
        "gloamfen_generation_selected": 0,
        "gloamfen_compile_eligible": True,
        "silkspire_accepted": silkspire["accepted_source_count"],
        "silkspire_generation_selected": silkspire["selected_generation_count"],
        "silkspire_compile_eligible": silkspire["compile_eligible"],
        "silkspire_exact_eight_accounting": True,
        "accepted_id_refusal_test": "PASS",
        "individual_asset_acceptance_supported": True,
        "state_resolution_mode_independent": True,
        "live_batch_cap_min": 1,
        "live_batch_cap_max": MAX_LIVE_BATCH_SIZE,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "production_frozen": True,
        "runtime_import_proof": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolve", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--plan-region")
    parser.add_argument("--request-id", action="append", default=[])
    args = parser.parse_args()
    if sum(bool(x) for x in [args.resolve, args.self_test, args.plan_region]) != 1:
        parser.error("choose exactly one of --resolve, --self-test, or --plan-region")
    if args.resolve:
        result = resolve_state()
    elif args.self_test:
        result = self_test()
    else:
        result = plan_region(args.plan_region, args.request_id or None)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
