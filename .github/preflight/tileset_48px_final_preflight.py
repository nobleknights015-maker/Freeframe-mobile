"""Zero-spend preflight for the Plushbound 48px RPG Maker MV tileset lane."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / ".github/preflight/tileset_48px_final_preflight_contract.json"
WORLD_CLOSEOUT_PATH = ROOT / "modal_worker/world_map_environment_master_baseline_closeout.json"
CREATOR_PATH = ROOT / "modal_worker/creator_full_outfits_half_scope_contract.json"
PRESETS_PATH = ROOT / "modal_worker/production_presets.py"

EXPECTED_GEOMETRY = {
    "A1": (768, 576),
    "A2": (768, 576),
    "A3": (768, 384),
    "A4": (768, 720),
    "A5": (384, 768),
    "B": (768, 768),
    "C": (768, 768),
    "D": (768, 768),
    "E": (768, 768),
}
EXPECTED_REGIONS = {
    "elyndor", "crownweave", "silkspire", "gloamfen", "verdancia",
    "tideglass-coast", "moonpatch-steppe", "sunspool-desert", "cinderreach", "frostlace",
}


def load_json(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"required evidence missing: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    contract = load_json(CONTRACT_PATH)
    world = load_json(WORLD_CLOSEOUT_PATH)
    creator = load_json(CREATOR_PATH)

    checks: dict[str, str] = {}

    if os.environ.get("PLUSHBOUND_PRODUCTION_ENABLED", "0") not in {"0", "false", "False", ""}:
        raise RuntimeError("tileset preflight refuses to run with production enabled")
    if os.environ.get("PLUSHBOUND_PAID_REMOTE_ENABLED", "0") not in {"0", "false", "False", ""}:
        raise RuntimeError("tileset preflight refuses to run with paid remote execution enabled")
    checks["zero_spend_environment"] = "PASS"

    gate = contract["spend_gate"]
    assert gate["production_enabled"] is False
    assert gate["paid_remote_execution_allowed"] is False
    assert gate["provider_calls_allowed"] == 0
    assert gate["gpu_calls_allowed"] == 0
    assert gate["generation_jobs_allowed"] == 0
    assert gate["catalog_wide_launch_authorized"] is False
    checks["contract_spend_gate"] = "PASS"

    assert world["status"] == "COMPLETE_10_OF_10_VISUAL_AND_DETERMINISTIC"
    assert world["canonical_region_count"] == 10
    assert world["accepted_count"] == 10
    assert world["quarantined_count"] == 0
    assert world["protected_from_rerender"] is True
    assert len(world["accepted_assets"]) == 10
    checks["world_environment_master_lock"] = "PASS"

    assert creator.get("final_total") == 24
    assert creator.get("completion_verified") is True
    assert creator.get("full_outfits_current_pass_closed") is True
    checks["creator_24_lock"] = "PASS"

    geom = contract["mv_geometry_contract"]
    assert geom["tile_width"] == 48 and geom["tile_height"] == 48
    for slot, (width, height) in EXPECTED_GEOMETRY.items():
        assert geom[slot]["width"] == width
        assert geom[slot]["height"] == height
    assert geom["A5"]["grid_columns"] == 8 and geom["A5"]["grid_rows"] == 16
    for slot in ("B", "C", "D", "E"):
        assert geom[slot]["grid_columns"] == 16 and geom[slot]["grid_rows"] == 16
    assert geom["B"]["top_left_tile_must_be_blank"] is True
    checks["mv_48px_geometry"] = "PASS"

    assert set(contract["canonical_regions"]) == EXPECTED_REGIONS
    assert len(contract["canonical_regions"]) == 10
    checks["canonical_regions"] = "PASS"

    arch = contract["production_architecture_requirement"]
    assert arch["world_editor_must_not_infer_layout_visually"] is True
    assert arch["generated_source_art_may_not_define_final_sheet_coordinates"] is True
    assert arch["final_sheet_must_be_compiled_to_locked_mv_slots"] is True
    assert arch["autotile_topology_must_be_validated"] is True
    assert arch["B_top_left_blank_validation_required"] is True
    checks["deterministic_compiler_requirement"] = "PASS"

    presets_text = PRESETS_PATH.read_text(encoding="utf-8")
    assert '"plushbound_tileset"' not in presets_text
    modal_worker_tileset_files = sorted(
        str(p.relative_to(ROOT)) for p in (ROOT / "modal_worker").rglob("*")
        if p.is_file() and "tileset" in p.name.lower()
    )
    if modal_worker_tileset_files:
        raise RuntimeError(f"unexpected existing tileset implementation requires re-audit: {modal_worker_tileset_files}")
    assert contract["branch_audit"]["production_preset_present"] is False
    assert contract["branch_audit"]["conclusion"] == "NO_EXISTING_FINAL_TILESET_PRODUCTION_ROUTE_FOUND"
    checks["existing_route_absence_confirmed"] = "PASS"

    catalog = contract["catalog_policy"]
    assert catalog["maximum_full_capacity_sheet_count_for_10_regions"] == 90
    assert catalog["do_not_generate_90_blindly"] is True
    assert catalog["require_region_sheet_occupancy_manifest_before_paid_generation"] is True
    assert catalog["require_first_bounded_canary_after_compiler_is_green"] is True
    checks["catalog_fail_closed"] = "PASS"

    report = {
        "schema": "plushbound.tileset_48px_final_preflight_report.v1",
        "status": "PASS_NO_SPEND_ROUTE_NOT_YET_AUTHORIZED",
        "production_skipped": True,
        "paid_remote_execution_skipped": True,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "tile_size": [48, 48],
        "sheet_geometry": {k: {"width": v[0], "height": v[1]} for k, v in EXPECTED_GEOMETRY.items()},
        "canonical_region_count": 10,
        "protected_environment_master_count": 10,
        "existing_tileset_production_route": False,
        "paid_tileset_generation_authorized": False,
        "next_action": contract["next_action_after_green_preflight"],
        "checks": checks,
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
