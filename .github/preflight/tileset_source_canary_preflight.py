"""Zero-spend validation for the first Plushbound tileset source-art canary."""
from __future__ import annotations

import json
import os
from pathlib import Path

from modal_worker.production_inspector import asset_class_for_item
from modal_worker.production_request_builder import build_production_request
from modal_worker.tileset_mv_compiler import load_manifest
from modal_worker.tileset_source_normalizer import self_test as normalizer_self_test

ROOT = Path(__file__).resolve().parents[2]
CANARY_PATH = ROOT / "modal_worker/tileset_source_canary_manifest.json"
OCCUPANCY_PATH = ROOT / "modal_worker/tileset_region_sheet_occupancy_manifest.json"
WORLD_CLOSEOUT_PATH = ROOT / "modal_worker/world_map_environment_master_baseline_closeout.json"

EXPECTED_IDS = {
    "tileset.elyndor.a5.source.lush_grass",
    "tileset.elyndor.a5.source.wildflower_grass",
    "tileset.elyndor.a5.source.warm_soil",
    "tileset.elyndor.a5.source.dirt_path",
    "tileset.elyndor.a5.source.tilled_farm_soil",
    "tileset.elyndor.a5.source.pale_field_stone",
    "tileset.elyndor.a5.source.village_timber",
    "tileset.elyndor.a5.source.straw_thatch",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if os.environ.get("PLUSHBOUND_PRODUCTION_ENABLED", "0") not in {"0", "false", "False", ""}:
        raise RuntimeError("source canary preflight refuses production-enabled environment")
    if os.environ.get("PLUSHBOUND_PAID_REMOTE_ENABLED", "0") not in {"0", "false", "False", ""}:
        raise RuntimeError("source canary preflight refuses paid-remote-enabled environment")

    canary = load_json(CANARY_PATH)
    world = load_json(WORLD_CLOSEOUT_PATH)
    occupancy = load_manifest(OCCUPANCY_PATH)
    checks: dict[str, str] = {}

    assert world["status"] == "COMPLETE_10_OF_10_VISUAL_AND_DETERMINISTIC"
    assert world["accepted_count"] == 10
    assert world["protected_from_rerender"] is True
    checks["world_reference_lock"] = "PASS"

    assert canary["schema"] == "plushbound.tileset_source_canary.v1"
    assert canary["status"] == "PREFLIGHT_ONLY_NOT_TRIGGERED"
    assert canary["region"] == "elyndor"
    assert canary["target_sheet_type"] == "A5"
    assert canary["source_preset"] == "plushbound_tileset_source"
    assert canary["source_master_size"] == [384, 384]
    assert canary["normalized_tile_size"] == [48, 48]
    assert canary["source_count"] == 8
    assert canary["paid_execution_authorized"] is False
    assert canary["catalog_wide_launch_authorized"] is False
    assert canary["creator_full_outfits_remain_closed_at"] == 24
    materials = canary["materials"]
    assert len(materials) == 8
    assert {row["asset_id"] for row in materials} == EXPECTED_IDS
    assert len({row["material_key"] for row in materials}) == 8
    assert all(str(row["prompt"]).strip() for row in materials)
    checks["exact_eight_source_manifest"] = "PASS"

    assert "A5" in occupancy["regions"]["elyndor"]["phase1"]
    assert occupancy["paid_generation_authorized"] is False
    checks["occupancy_target"] = "PASS"

    route_rows = []
    for index, row in enumerate(materials):
        request = build_production_request(
            "plushbound_tileset_source",
            str(row["prompt"]),
            seed=17001 + index,
        )
        assert request["width"] == 384 and request["height"] == 384
        assert request["steps"] == 4
        assert request["guidance_scale"] == 1.0
        assert request["model_id"] == "black-forest-labs/FLUX.2-klein-4B"
        assert request["renderer_route"] == "flux2_klein"
        assert request["bounded_production_authorized"] is True
        assert request["automatic_full_production_authorized"] is False
        assert request["catalog_wide_launch_authorized"] is False
        assert request["production_style_validated"] is True
        assert request["production_style_profile"] == "plushbound_tileset_source"
        assert request["style_preset"] == "plushbound_tileset_source"
        assert asset_class_for_item({"preset":"plushbound_tileset_source"}) == "tileset_master"
        negative = str(request.get("negative_prompt", "")).lower()
        for forbidden in ("tile grid", "checkerboard", "contact sheet", "signage", "typography"):
            assert forbidden in negative
        route_rows.append({
            "asset_id": row["asset_id"],
            "seed": request["seed"],
            "width": request["width"],
            "height": request["height"],
            "steps": request["steps"],
            "guidance_scale": request["guidance_scale"],
            "model_id": request["model_id"],
            "renderer_route": request["renderer_route"],
            "style_profile": request["production_style_profile"],
        })
    checks["request_builder_route"] = "PASS"

    norm = normalizer_self_test()
    assert norm["status"] == "PASS"
    assert norm["output_size"] == [48, 48]
    assert norm["output_mode"] == "RGBA"
    checks["normalizer_self_test"] = "PASS"

    contract = canary["normalization_contract"]
    assert contract["input_width"] == 384 and contract["input_height"] == 384
    assert contract["output_width"] == 48 and contract["output_height"] == 48
    assert contract["deterministic_downsample"] == "LANCZOS"
    assert contract["visual_semantic_qa_required"] is True
    assert canary["scale_policy"]["do_not_generate_full_A5_after_machine_pass_alone"] is True
    assert canary["scale_policy"]["manual_visual_pass_required_before_any_expansion"] is True
    checks["scale_fail_closed"] = "PASS"

    report = {
        "schema": "plushbound.tileset_source_canary_preflight_report.v1",
        "status": "PASS_NO_SPEND_SOURCE_CANARY_NOT_TRIGGERED",
        "production_skipped": True,
        "paid_remote_execution_skipped": True,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "source_count": 8,
        "source_master_size": [384,384],
        "normalized_tile_size": [48,48],
        "target_region": "elyndor",
        "target_sheet_type": "A5",
        "paid_tileset_source_canary_authorized": False,
        "normalizer_self_test": norm,
        "request_routes": route_rows,
        "checks": checks,
        "next_action": "SEPARATE_EXPLICIT_EIGHT_SOURCE_PAID_CANARY_TRIGGER_AFTER_THIS_GREEN_PREFLIGHT",
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
