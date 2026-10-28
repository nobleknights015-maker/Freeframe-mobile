"""Zero-spend per-region preflight for remaining Plushbound Engine v1 A5 tilesets."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from modal_worker.engine_v1_a5_compatibility_validator import (
    EXPECTED_COLUMNS, EXPECTED_HEIGHT, EXPECTED_ROWS, EXPECTED_SLOTS,
    EXPECTED_WIDTH, PROFILE as ENGINE_PROFILE, TILE_SIZE as VALIDATOR_TILE_SIZE,
)
from modal_worker.production_inspector import asset_class_for_item
from modal_worker.production_request_builder import build_production_request
from modal_worker.tileset_regional_a5_compiler import self_test as compiler_self_test
from modal_worker.tileset_source_normalizer import self_test as normalizer_self_test

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "modal_worker/tileset_regional_a5_scope_manifest.json"
OCCUPANCY = ROOT / "modal_worker/tileset_region_sheet_occupancy_manifest.json"
AUDIT = ROOT / "modal_worker/plushbound_final_asset_lane_audit_2026-10-28.json"
ELYNDOR = ROOT / "modal_worker/tileset_elyndor_a5_engine_v1_compatibility.json"
REMAINING = {
    "crownweave", "silkspire", "gloamfen", "verdancia", "tideglass-coast",
    "moonpatch-steppe", "sunspool-desert", "cinderreach", "frostlace",
}
ALLOWED_REGION_STATES = {"PREFLIGHT_PENDING", "QUARANTINED_PROMPT_REPAIR_REQUIRED"}
FORBIDDEN_MATERIAL_LABEL_SCENE_TERMS = {
    "bridge", "building", "ruin", "tree", "bush", "pond", "river", "path",
    "road", "character", "creature", "furniture", "tool", "prop", "debris",
    "boardwalk", "marsh", "forest", "harbor", "caravan", "shelter", "desert",
    "volcanic", "archive", "workshop", "city", "settlement", "diorama",
    "landscape", "game level",
}


def load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing evidence: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(value: bool, message: str) -> None:
    if not value:
        raise RuntimeError(message)


def run(region: str) -> dict:
    require(os.environ.get("PLUSHBOUND_PRODUCTION_ENABLED", "0") in {"0", "false", "False", ""}, "production enabled")
    require(os.environ.get("PLUSHBOUND_PAID_REMOTE_ENABLED", "0") in {"0", "false", "False", ""}, "paid remote enabled")
    scope, occ, audit, ely = load(SCOPE), load(OCCUPANCY), load(AUDIT), load(ELYNDOR)
    checks: dict[str, str] = {}

    require(scope["schema"] == "plushbound.tileset_regional_a5_scope_manifest.v1", "scope schema drift")
    require(scope["status"] == "PREFLIGHT_ONLY_NO_SPEND", "scope not fail-closed")
    require(set(scope["remaining_regions"]) == REMAINING and region in REMAINING, "unfinished region set drift")
    require(region != "elyndor", "Elyndor is closed")
    checks["unfinished_region_scope"] = "PASS"

    lock = scope["closed_regions"]["elyndor"]
    require(lock["status"] == "CLOSED_BANKED", "Elyndor lock changed")
    require(lock["engine_v1_sha256"] == "d26595d093676bfd0bdfc44259a7795674d96dc4925f6db5773efa06e044a1bb", "Elyndor hash changed")
    require(ely["status"] == "PASS_ENGINE_V1_COMPATIBILITY_CONTRACT", "Elyndor closeout not green")
    require(ely["compiled_sheet_sha256"] == lock["engine_v1_sha256"], "Elyndor hash evidence mismatch")
    require(ely["runtime_import_proof"] is False, "invalid runtime-import claim")
    require(ely["accepted_source_ids_protected_from_rerender"] is True, "Elyndor sources not protected")
    checks["elyndor_immutable_closeout"] = "PASS"

    rules, lanes = audit["rules"], audit["lanes"]
    require(rules["creator_full_outfits_closed_at"] == 24, "creator lock changed")
    require(rules["do_not_redo_finished_lanes"] is True, "finished-lane protection changed")
    require(rules["missing_local_artifact_is_not_rerender_authority"] is True, "missing-local policy changed")
    require(lanes["guardians"]["verified_runtime_asset_count"] == 960, "guardian lock changed")
    require(lanes["npcs"]["verified_mv_asset_count"] == 320, "NPC lock changed")
    e = lanes["enemies_bosses"]
    require([e["runtime_banked_count"], e["runtime_quarantined_count"], e["runtime_accounted_count"]] == [617, 23, 640], "enemy accounting changed")
    require(audit["catalog_wide_launch_authorized"] is False, "catalog-wide launch enabled")
    checks["completed_lane_locks"] = "PASS"

    require(occ["schema"] == "plushbound.tileset_region_sheet_occupancy.v1", "occupancy schema drift")
    require(region in occ["regions"] and "A5" in occ["regions"][region]["phase1"], "A5 inactive for region")
    require(occ["sheet_geometry"]["A5"] == [384, 768] and occ["tile_size"] == [48, 48], "occupancy geometry drift")
    require(occ["stable_id_format"] == "tileset.<region>.<sheet_type_lower>", "stable ID format drift")
    require(occ["paid_generation_authorized"] is False, "occupancy unexpectedly authorizes paid generation")
    checks["occupancy_contract"] = "PASS"

    engine = scope["engine_contract"]
    require(engine["profile"] == ENGINE_PROFILE, "engine profile drift")
    require(engine["sheet_size"] == [EXPECTED_WIDTH, EXPECTED_HEIGHT] == [384, 768], "A5 sheet geometry drift")
    require(engine["tile_size"] == [VALIDATOR_TILE_SIZE, VALIDATOR_TILE_SIZE] == [48, 48], "tile geometry drift")
    require(engine["grid"] == [EXPECTED_COLUMNS, EXPECTED_ROWS] == [8, 16], "grid drift")
    require(engine["slot_count"] == EXPECTED_SLOTS == 128, "slot count drift")
    checks["engine_v1_geometry_contract"] = "PASS"

    spend = scope["spend_gate"]
    require(spend["production_enabled"] is False and spend["paid_remote_execution_allowed"] is False, "preflight spend gate enabled")
    require([spend["provider_calls_allowed"], spend["gpu_calls_allowed"], spend["generation_jobs_allowed"]] == [0, 0, 0], "preflight spend allowance changed")
    require(spend["catalog_wide_launch_authorized"] is False, "catalog-wide launch enabled")
    require(spend["never_stack_paid_runs"] is True and spend["one_region_per_paid_trigger"] is True, "bounded-run safety changed")
    checks["zero_spend_gate"] = "PASS"

    rs = scope["regions"][region]
    require(rs["status"] in ALLOWED_REGION_STATES and rs["sheet_type"] == "A5", "regional state drift")
    require(rs["stable_sheet_id"] == f"tileset.{region}.a5", "sheet stable ID mismatch")
    materials = rs["materials"]
    require(len(materials) == 8 and len(set(materials)) == 8, "must have exactly eight unique materials")
    require(all(isinstance(m, str) and m and m.replace("_", "").replace("-", "").isalnum() for m in materials), "invalid material key")
    region_hint = str(rs.get("region_material_hint", "")).strip()
    require(region_hint != "", "blank region material hint")
    labels = rs.get("material_prompt_labels")
    require(isinstance(labels, dict) and set(labels) == set(materials), "material prompt labels must exactly match stable material keys")
    require(all(isinstance(labels[m], str) and labels[m].strip() for m in materials), "blank material prompt label")
    checks["exact_eight_material_scope"] = "PASS"

    if rs["status"] == "QUARANTINED_PROMPT_REPAIR_REQUIRED":
        quarantine_path = ROOT / str(rs.get("quarantine_evidence", ""))
        quarantine = load(quarantine_path)
        require(quarantine["schema"] == "plushbound.tileset_regional_a5_source_quarantine.v1", "quarantine schema drift")
        require(quarantine["region"] == region and quarantine["target_sheet_type"] == "A5", "quarantine target mismatch")
        require(quarantine["status"] == "QUARANTINED_MANUAL_VISUAL_FAIL_0_OF_8_ACCEPTED", "quarantine status drift")
        require(quarantine["accepted_source_count"] == 0 and quarantine["quarantined_source_count"] == 8, "quarantine accounting drift")
        require(quarantine["compile_authorized"] is False and quarantine["deterministic_finalize_authorized"] is False, "quarantine unexpectedly authorizes compile")
        require(quarantine["catalog_wide_launch_authorized"] is False, "quarantine unexpectedly authorizes catalog launch")
        checks["quarantine_evidence_bound"] = "PASS"

    sc = scope["source_contract"]
    require(sc["preset"] == "plushbound_tileset_source", "source preset drift")
    require(sc["source_master_size"] == [384, 384] and sc["normalized_tile_size"] == [48, 48], "source geometry drift")
    require([sc["materials_per_region"], sc["variants_per_material"], sc["generation_attempts_per_material_cap"]] == [8, 16, 1], "source count/retry cap drift")
    require(sc.get("prompt_contract_version") == "regional-a5-material-swatch-v2", "source prompt contract version drift")
    template = str(sc.get("prompt_template", ""))
    required_phrases = [str(x).lower() for x in sc.get("required_prompt_phrases", [])]
    require(len(required_phrases) >= 30, "anti-scene prompt phrase contract is incomplete")
    forbidden_hint_terms = [str(x).lower() for x in sc.get("forbidden_region_hint_terms", [])]
    hint_lower = region_hint.lower()
    require(not any(term in hint_lower for term in forbidden_hint_terms), "region material hint contains scene-inducing noun")
    for material in materials:
        label_lower = labels[material].lower()
        require(not any(term in label_lower for term in FORBIDDEN_MATERIAL_LABEL_SCENE_TERMS), f"{material}: prompt label contains scene-inducing noun")
    checks["material_swatch_prompt_static_lint"] = "PASS"
    checks["source_geometry_and_retry_cap"] = "PASS"

    routes = []
    for i, material in enumerate(materials):
        asset_id = f"tileset.{region}.a5.source.{material}"
        prompt = template.format(region_material_hint=region_hint, material_name=labels[material])
        prompt_lower = prompt.lower()
        require(all(phrase in prompt_lower for phrase in required_phrases), f"{asset_id}: anti-scene prompt contract incomplete")
        request = build_production_request("plushbound_tileset_source", prompt, seed=28001 + i)
        expected = {
            "width": 384, "height": 384, "steps": 4, "guidance_scale": 1.0,
            "model_id": "black-forest-labs/FLUX.2-klein-4B", "renderer_route": "flux2_klein",
            "bounded_production_authorized": True, "automatic_full_production_authorized": False,
            "catalog_wide_launch_authorized": False, "production_style_validated": True,
            "production_style_profile": "plushbound_tileset_source", "style_preset": "plushbound_tileset_source",
        }
        require(all(request.get(k) == v for k, v in expected.items()), f"{asset_id}: request route drift")
        require(asset_class_for_item({"preset": "plushbound_tileset_source"}) == "tileset_master", "asset class drift")
        negative = str(request.get("negative_prompt", "")).lower()
        require(all(x in negative for x in ("tile grid", "checkerboard", "contact sheet", "signage", "typography")), f"{asset_id}: negative prompt drift")
        routes.append({
            "asset_id": asset_id,
            "seed_probe": request["seed"],
            "width": 384,
            "height": 384,
            "steps": 4,
            "guidance_scale": 1.0,
            "model_id": request["model_id"],
            "renderer_route": request["renderer_route"],
            "prompt_contract_version": sc["prompt_contract_version"],
            "prompt_sha256": __import__("hashlib").sha256(prompt.encode("utf-8")).hexdigest(),
        })
    checks["bounded_request_route"] = "PASS"
    checks["rendered_prompt_anti_scene_contract"] = "PASS"

    norm = normalizer_self_test()
    require(norm["status"] == "PASS" and norm["output_size"] == [48, 48] and norm["output_mode"] == "RGBA", "normalizer self-test failed")
    checks["normalizer_self_test"] = "PASS"
    comp = compiler_self_test(region)
    require(comp["status"] == "PASS" and comp["sheet_size"] == [384, 768] and comp["grid"] == [8, 16] and comp["slot_count"] == 128, "compiler self-test failed")
    require([comp["provider_calls"], comp["gpu_calls"], comp["generation_calls"]] == [0, 0, 0], "compiler self-test spent resources")
    checks["deterministic_compiler_self_test"] = "PASS"

    return {
        "schema": "plushbound.tileset_regional_a5_preflight_report.v1",
        "status": "PASS_NO_SPEND_REGION_A5_READY_FOR_EXPLICIT_BOUNDED_TRIGGER",
        "region": region,
        "region_state": rs["status"],
        "sheet_type": "A5",
        "stable_sheet_id": rs["stable_sheet_id"],
        "prompt_contract_version": sc["prompt_contract_version"],
        "production_skipped": True,
        "paid_remote_execution_skipped": True,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "source_count": 8,
        "source_master_size": [384, 384],
        "sheet_geometry": [384, 768],
        "tile_geometry": [48, 48],
        "grid": [8, 16],
        "slot_count": 128,
        "preflight_authorizes_one_explicit_bounded_region_trigger": True,
        "automatic_paid_execution_authorized": False,
        "catalog_wide_launch_authorized": False,
        "accepted_assets_immutable": True,
        "runtime_import_proof": False,
        "normalizer_self_test": norm,
        "compiler_self_test": comp,
        "request_routes": routes,
        "checks": checks,
        "next_action": "BANK_THIS_GREEN_PREFLIGHT_RUN_ID_THEN_TRIGGER_ONLY_AN_EXPLICIT_BOUNDED_REGION_OR_REPAIR_PROBE_IF_GPU_BUDGET_ALLOWS",
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--region", required=True)
    args = p.parse_args()
    print(json.dumps(run(args.region), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
