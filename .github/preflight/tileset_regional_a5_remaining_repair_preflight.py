"""Zero-spend preflight for the seven-source remainder after one accepted A5 repair probe."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from modal_worker.production_request_builder import build_production_request
from modal_worker.tileset_regional_a5_compiler import self_test as compiler_self_test
from modal_worker.tileset_regional_a5_partial_acceptance_validator import validate as validate_partial

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "modal_worker/tileset_regional_a5_scope_manifest.json"
POLICY = ROOT / "modal_worker/tileset_regional_a5_repair_policy.json"
AUDIT = ROOT / "modal_worker/plushbound_final_asset_lane_audit_2026-10-28.json"
PROMPT_VERSION = "regional-a5-material-swatch-v2"


def load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing required evidence: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run(region: str) -> dict:
    require(os.environ.get("PLUSHBOUND_PRODUCTION_ENABLED", "0") in {"0", "false", "False", ""}, "production enabled during repair preflight")
    require(os.environ.get("PLUSHBOUND_PAID_REMOTE_ENABLED", "0") in {"0", "false", "False", ""}, "paid remote enabled during repair preflight")
    scope, policy, audit = load(SCOPE), load(POLICY), load(AUDIT)
    checks: dict[str, str] = {}

    require(scope["schema"] == "plushbound.tileset_regional_a5_scope_manifest.v1", "scope schema drift")
    require(policy["schema"] == "plushbound.tileset_regional_a5_repair_policy.v1", "repair policy schema drift")
    require(policy["prompt_contract_version"] == PROMPT_VERSION, "repair policy prompt version drift")
    require(region != "elyndor" and region in scope["remaining_regions"], "repair region is closed/unknown")
    regional = scope["regions"][region]
    require(regional["status"] == "REPAIR_PARTIAL_1_OF_8_ACCEPTED", "remaining repair requires partial-acceptance region state")
    require(regional["sheet_type"] == "A5" and regional["stable_sheet_id"] == f"tileset.{region}.a5", "regional A5 identity drift")
    partial_path = ROOT / str(regional.get("partial_acceptance_evidence", ""))
    partial_validation = validate_partial(partial_path, region)
    require(partial_validation["status"] == "PASS_PARTIAL_ACCEPTANCE_PROBE_GREEN_1_OF_8", "partial acceptance validation failed")
    partial = load(partial_path)
    checks["partial_acceptance_green_1_of_8"] = "PASS"

    rules, lanes = audit["rules"], audit["lanes"]
    require(rules["creator_full_outfits_closed_at"] == 24, "creator lock changed")
    require(rules["do_not_redo_finished_lanes"] is True, "finished lane protection changed")
    require(rules["missing_local_artifact_is_not_rerender_authority"] is True, "missing-local rerender policy changed")
    require(lanes["guardians"]["verified_runtime_asset_count"] == 960, "guardian lock changed")
    require(lanes["npcs"]["verified_mv_asset_count"] == 320, "NPC lock changed")
    enemy = lanes["enemies_bosses"]
    require([enemy["runtime_banked_count"], enemy["runtime_quarantined_count"], enemy["runtime_accounted_count"]] == [617, 23, 640], "enemy accounting changed")
    require(audit["catalog_wide_launch_authorized"] is False, "catalog-wide launch enabled")
    checks["completed_lane_locks"] = "PASS"

    spend = scope["spend_gate"]
    require(spend["production_enabled"] is False and spend["paid_remote_execution_allowed"] is False, "scope spend gate enabled")
    require([spend["provider_calls_allowed"], spend["gpu_calls_allowed"], spend["generation_jobs_allowed"]] == [0, 0, 0], "scope preflight spend allowance changed")
    require(spend["catalog_wide_launch_authorized"] is False and spend["never_stack_paid_runs"] is True and spend["one_region_per_paid_trigger"] is True, "bounded spend safety drift")
    checks["zero_spend_gate"] = "PASS"

    accepted_ids = set(partial["accepted_source_ids"])
    remaining_ids = list(partial["remaining_failed_source_ids"])
    require(len(accepted_ids) == 1 and len(remaining_ids) == 7 and len(set(remaining_ids)) == 7, "repair accounting must be 1 accepted + 7 remaining")
    require(not accepted_ids.intersection(remaining_ids), "accepted probe source appears in remaining repair")
    materials = regional["materials"]
    expected_all = {f"tileset.{region}.a5.source.{m}" for m in materials}
    require(accepted_ids.union(remaining_ids) == expected_all, "accepted + remaining IDs do not exactly account for regional A5 sources")
    require(partial["accepted_source_ids_protected_from_rerender"] is True, "accepted probe ID not protected")
    checks["accepted_id_exclusion"] = "PASS"

    source = scope["source_contract"]
    require(source["prompt_contract_version"] == PROMPT_VERSION, "scope prompt contract drift")
    require(source["generation_attempts_per_material_cap"] == 1, "generation attempt cap drift")
    hint = str(regional["region_material_hint"]).strip()
    labels = regional["material_prompt_labels"]
    require(set(labels) == set(materials), "material prompt label scope drift")
    required_phrases = [str(x).lower() for x in source["required_prompt_phrases"]]
    routes = []
    prefix = f"tileset.{region}.a5.source."
    for i, asset_id in enumerate(remaining_ids):
        require(asset_id.startswith(prefix), "repair asset outside regional stable-ID namespace")
        material = asset_id[len(prefix):]
        require(material in materials, "repair material outside locked scope")
        prompt = source["prompt_template"].format(region_material_hint=hint, material_name=labels[material])
        require(all(phrase in prompt.lower() for phrase in required_phrases), f"{asset_id}: repaired prompt anti-scene contract incomplete")
        request = build_production_request("plushbound_tileset_source", prompt, seed=29001 + i)
        expected = {
            "width": 384,
            "height": 384,
            "steps": 4,
            "guidance_scale": 1.0,
            "model_id": "black-forest-labs/FLUX.2-klein-4B",
            "renderer_route": "flux2_klein",
            "bounded_production_authorized": True,
            "automatic_full_production_authorized": False,
            "catalog_wide_launch_authorized": False,
            "production_style_profile": "plushbound_tileset_source",
            "style_preset": "plushbound_tileset_source",
        }
        require(all(request.get(k) == v for k, v in expected.items()), f"{asset_id}: bounded request route drift")
        routes.append({
            "asset_id": asset_id,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "seed_probe": request["seed"],
            "model_id": request["model_id"],
            "renderer_route": request["renderer_route"],
        })
    require(len(routes) == 7, "remaining repair route count drift")
    checks["seven_source_prompt_v2_routes"] = "PASS"

    comp = compiler_self_test(region)
    require(comp["status"] == "PASS" and comp["sheet_size"] == [384, 768] and comp["grid"] == [8, 16] and comp["slot_count"] == 128, "deterministic compiler self-test failed")
    require([comp["provider_calls"], comp["gpu_calls"], comp["generation_calls"]] == [0, 0, 0], "compiler self-test spent resources")
    checks["deterministic_compiler_self_test"] = "PASS"

    repair = policy["remaining_repair"]
    require(repair["authorized_only_after_probe_manual_pass_is_banked"] is True, "repair policy weakened")
    require(repair["accepted_source_ids_immutable"] is True and repair["accepted_probe_source_must_not_be_rerendered"] is True, "accepted source immutability weakened")
    require(repair["one_region_only"] is True and repair["never_stack_paid_runs"] is True and repair["catalog_wide_launch_authorized"] is False, "repair boundedness weakened")
    checks["repair_policy"] = "PASS"

    return {
        "schema": "plushbound.tileset_regional_a5_remaining_repair_preflight.v1",
        "status": "PASS_NO_SPEND_REMAINING_REPAIR_7_READY_FOR_EXPLICIT_TRIGGER",
        "region": region,
        "stable_sheet_id": regional["stable_sheet_id"],
        "prompt_contract_version": PROMPT_VERSION,
        "accepted_source_ids": sorted(accepted_ids),
        "remaining_source_ids": remaining_ids,
        "accepted_source_count": 1,
        "remaining_repair_source_count": 7,
        "generation_attempts_per_remaining_asset_cap": 1,
        "production_skipped": True,
        "paid_remote_execution_skipped": True,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "compile_authorized": False,
        "deterministic_finalize_authorized": False,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
        "request_routes": routes,
        "checks": checks,
        "next_action": "EXPLICITLY_TRIGGER_ONLY_THE_SEVEN_REMAINING_FAILED_SOURCE_IDS_IF_GPU_BUDGET_ALLOWS"
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.region), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
