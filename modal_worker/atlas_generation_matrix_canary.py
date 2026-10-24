"""Bounded four-lane Atlas production canary.

This exercises every currently supported generated master family through the same
Atlas plan -> FreeFrame production gateway -> deterministic inspection -> Atlas
ledger path. It never promotes a render to accepted without human semantic review
and never authorizes catalog-wide production.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import modal

from modal_worker.atlas_controller import plan_asset
from modal_worker.atlas_production_ledger import AssetProductionRecord, transition, verify_history
from modal_worker.production_inspector import inspect_generation

CANARY_VERSION = "atlas-generation-matrix-v1-klein-bounded"
EXPECTED_MODEL = "black-forest-labs/FLUX.2-klein-4B"
EXPECTED_ROUTE = "flux2_klein"
REPORT_JSON = Path("atlas-generation-matrix-report.json")

CASES = (
    {
        "case_id": "character_elyndor_courier",
        "intent": {
            "family": "character_master",
            "description": (
                "original adult Elyndor field courier and junior adventurer, practical layered travel clothes, "
                "sun-warmed plains palette, satchel and weathered boots, approachable but capable, full body"
            ),
            "seed": 826104,
        },
        "preset": "plushbound_character",
        "asset_class": "character_master",
    },
    {
        "case_id": "guardian_elyndor_meadow",
        "intent": {
            "family": "guardian_friendly",
            "description": (
                "one original small meadow Guardian species with leaf-shaped ears, compact quadruped anatomy, "
                "warm amber thread markings, alert natural creature expression, full creature visible"
            ),
            "context": {"region": "Elyndor"},
            "seed": 826105,
        },
        "preset": "plushbound_guardian",
        "asset_class": "guardian_master",
    },
    {
        "case_id": "enemy_elyndor_prowler",
        "intent": {
            "family": "enemy_creature",
            "description": (
                "one original Elyndor woodland prowler, low four-legged hostile living-textile creature, "
                "long horizontal torso, four clearly separated weight-bearing legs and paws, full creature visible"
            ),
            "context": {"region": "Elyndor"},
            "seed": 826106,
        },
        "preset": "plushbound_enemy",
        "asset_class": "enemy_master",
    },
    {
        "case_id": "environment_elyndor_road",
        "intent": {
            "family": "environment_master",
            "description": (
                "sunny plains of Elyndor with a traversable winding dirt road, broad flower fields, distant handcrafted "
                "fantasy village, wooded hills and blue mountains, empty landscape with no foreground characters"
            ),
            "context": {"region": "Elyndor"},
            "seed": 826107,
        },
        "preset": "plushbound_environment",
        "asset_class": "environment_master",
    },
)


def _structural_checks(plan: dict, result: dict, raw: bytes) -> dict:
    request = plan["generation_request"]
    actual_sha = hashlib.sha256(raw).hexdigest()
    return {
        "png_signature_valid": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "nonempty_image": len(raw) > 1024,
        "width_matches": int(result.get("width", -1)) == int(request["width"]),
        "height_matches": int(result.get("height", -1)) == int(request["height"]),
        "sha256_matches": str(result.get("sha256", "")) == actual_sha,
        "seed_matches": int(result.get("seed", -1)) == int(plan["seed"]),
        "request_model_is_klein": request.get("model_id") == EXPECTED_MODEL,
        "result_model_is_klein": result.get("model") == EXPECTED_MODEL,
        "request_route_is_production": request.get("renderer_route") == EXPECTED_ROUTE,
        "result_route_is_production": result.get("renderer_route") == EXPECTED_ROUTE,
        "bounded_production_authorized": request.get("bounded_production_authorized") is True,
        "catalog_launch_still_locked": request.get("catalog_wide_launch_authorized") is False,
        "atlas_did_not_condition_visual_generation": plan.get("atlas_visual_conditioning") is None,
        "visual_generation_owner_is_vera": plan.get("visual_generation_owned_by") == "Vera",
    }


def main() -> None:
    gateway = modal.Function.from_name("freeframe-worker", "generate_image_internal")
    results = []

    for case in CASES:
        case_id = case["case_id"]
        plan = plan_asset(case["intent"])
        if not plan.get("generation_supported") or not isinstance(plan.get("generation_request"), dict):
            raise RuntimeError(f"{case_id}: Atlas did not produce a generation-ready request")

        record = AssetProductionRecord.from_dict(plan["ledger_record"])
        transition(record, "plan_validated", {
            "canary_version": CANARY_VERSION,
            "case_id": case_id,
            "expected_model": EXPECTED_MODEL,
            "expected_route": EXPECTED_ROUTE,
        })

        result = gateway.remote(plan["generation_request"])
        encoded = result.get("image_base64")
        if not encoded:
            transition(record, "generation_failed", {"reason": "worker returned no image_base64", "case_id": case_id})
            raise RuntimeError(f"{case_id}: FreeFrame returned no image")

        raw = base64.b64decode(encoded, validate=True)
        checks = _structural_checks(plan, result, raw)
        if not all(checks.values()):
            transition(record, "generation_failed", {"case_id": case_id, "structural_checks": checks})
            raise RuntimeError(f"{case_id}: structural checks failed: {checks}")

        inspection_item = {
            "preset": case["preset"],
            "asset_class": case["asset_class"],
        }
        inspection = inspect_generation(inspection_item, result)
        if not inspection["accepted"]:
            transition(record, "generation_succeeded", {
                "case_id": case_id,
                "render_sha256": result["sha256"],
                "deterministic_inspection": inspection,
            })
            transition(record, "qa_failed", {
                "case_id": case_id,
                "reason": "deterministic production inspection rejected render",
                "inspection": inspection,
            })
        else:
            transition(record, "generation_succeeded", {
                "case_id": case_id,
                "render_sha256": result["sha256"],
                "width": result["width"],
                "height": result["height"],
                "seed": result["seed"],
                "model": result.get("model"),
                "renderer_route": result.get("renderer_route"),
                "deterministic_inspection": inspection,
                "visual_qa": "pending_human_review",
            })
        verify_history(record)

        output = Path(f"atlas-matrix-{case_id}.png")
        output.write_bytes(raw)
        results.append({
            "case_id": case_id,
            "output": str(output),
            "intent": case["intent"],
            "atlas_job_id": plan["atlas_job_id"],
            "atlas_voice": plan.get("atlas_voice"),
            "request": plan["generation_request"],
            "result_metadata": {k: v for k, v in result.items() if k != "image_base64"},
            "structural_checks": checks,
            "deterministic_inspection": inspection,
            "ledger_record": record.to_dict(),
            "visual_qa": "pending_human_review" if inspection["accepted"] else "deterministic_rejection",
        })

    report = {
        "canary_version": CANARY_VERSION,
        "status": "generated_pending_human_visual_review",
        "model": EXPECTED_MODEL,
        "renderer_route": EXPECTED_ROUTE,
        "cases": results,
        "deterministic_pass_count": sum(1 for item in results if item["deterministic_inspection"]["accepted"]),
        "case_count": len(results),
        "automatic_full_production_authorized": False,
        "catalog_wide_launch_authorized": False,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "deterministic_pass_count": report["deterministic_pass_count"],
        "case_count": report["case_count"],
        "outputs": [item["output"] for item in results],
        "report": str(REPORT_JSON),
    }, indent=2))


if __name__ == "__main__":
    main()
