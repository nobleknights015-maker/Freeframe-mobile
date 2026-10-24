"""Bounded end-to-end canary for Atlas -> production gateway -> Atlas ledger.

This proves Atlas can create a real production plan whose exact generation request is
accepted by the deployed FreeFrame production gateway. It deliberately stops at the
`generated` ledger state: semantic visual/artistic approval remains a separate review.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import modal

from modal_worker.atlas_controller import plan_asset
from modal_worker.atlas_production_ledger import AssetProductionRecord, transition, verify_history

CANARY_VERSION = "atlas-generation-e2e-v4-civilian-fantasy-character"
OUTPUT_PNG = Path("atlas-e2e-character.png")
REPORT_JSON = Path("atlas-e2e-report.json")
EXPECTED_MODEL = "black-forest-labs/FLUX.2-klein-4B"
EXPECTED_ROUTE = "flux2_klein"


def _structural_checks(plan: dict, result: dict, raw: bytes) -> dict:
    request = plan["generation_request"]
    expected_width = int(request["width"])
    expected_height = int(request["height"])
    actual_sha = hashlib.sha256(raw).hexdigest()
    prompt = str(request.get("prompt", "")).lower()
    return {
        "png_signature_valid": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "nonempty_image": len(raw) > 1024,
        "width_matches": int(result.get("width", -1)) == expected_width,
        "height_matches": int(result.get("height", -1)) == expected_height,
        "sha256_matches": str(result.get("sha256", "")) == actual_sha,
        "seed_matches": int(result.get("seed", -1)) == int(plan["seed"]),
        "request_model_is_klein": request.get("model_id") == EXPECTED_MODEL,
        "result_model_is_klein": result.get("model") == EXPECTED_MODEL,
        "request_route_is_production": request.get("renderer_route") == EXPECTED_ROUTE,
        "result_route_is_production": result.get("renderer_route") == EXPECTED_ROUTE,
        "bounded_production_authorized": request.get("bounded_production_authorized") is True,
        "catalog_launch_still_locked": request.get("catalog_wide_launch_authorized") is False,
        "prompt_forbids_character_sheet": "no character-sheet layout" in prompt,
        "prompt_forbids_typography": "no typography" in prompt,
        "atlas_did_not_condition_visual_generation": plan.get("atlas_visual_conditioning") is None,
        "visual_generation_owner_is_vera": plan.get("visual_generation_owned_by") == "Vera",
    }


def main() -> None:
    intent = {
        "family": "character_master",
        "description": (
            "original adult Elyndor civilian pathfinder and message-runner wearing handcrafted fantasy travel attire: "
            "layered linen tunic, short asymmetrical woven mantle, leather shoulder satchel, simple belt pouches, cloth wrist wraps, "
            "soft travel trousers and weathered leather boots, warm plains palette, approachable and capable, full body"
        ),
        "seed": 826104,
    }
    plan = plan_asset(intent)
    if not plan.get("generation_supported") or not isinstance(plan.get("generation_request"), dict):
        raise RuntimeError("Atlas did not produce a generation-ready request")

    record = AssetProductionRecord.from_dict(plan["ledger_record"])
    transition(record, "plan_validated", {
        "canary_version": CANARY_VERSION,
        "scope": "single bounded character_master production-gateway test",
        "expected_model": EXPECTED_MODEL,
        "expected_route": EXPECTED_ROUTE,
    })

    gateway = modal.Function.from_name("freeframe-worker", "generate_image_internal")
    result = gateway.remote(plan["generation_request"])
    encoded = result.get("image_base64")
    if not encoded:
        transition(record, "generation_failed", {"reason": "worker returned no image_base64"})
        raise RuntimeError("FreeFrame production gateway returned no image")

    raw = base64.b64decode(encoded, validate=True)
    checks = _structural_checks(plan, result, raw)
    passed = all(checks.values())
    if not passed:
        transition(record, "generation_failed", {"structural_checks": checks})
        raise RuntimeError(f"end-to-end structural checks failed: {checks}")

    OUTPUT_PNG.write_bytes(raw)
    transition(record, "generation_succeeded", {
        "render_sha256": result["sha256"],
        "width": result["width"],
        "height": result["height"],
        "seed": result["seed"],
        "model": result.get("model"),
        "renderer_route": result.get("renderer_route"),
        "structural_checks": checks,
        "visual_qa": "pending_human_review",
    })
    verify_history(record)

    report = {
        "canary_version": CANARY_VERSION,
        "status": "generated_pending_visual_review",
        "intent": intent,
        "atlas": {
            "assistant_name": plan["assistant_name"],
            "controller_version": plan["controller_version"],
            "personality_version": plan.get("personality_version"),
            "atlas_voice": plan.get("atlas_voice"),
            "atlas_job_id": plan["atlas_job_id"],
            "plan_digest": plan["plan_digest"],
            "responsibility_boundary": plan["responsibility_boundary"],
        },
        "generation": {
            "request": plan["generation_request"],
            "result_metadata": {k: v for k, v in result.items() if k != "image_base64"},
            "structural_checks": checks,
        },
        "ledger_record": record.to_dict(),
        "visual_qa": "pending_human_review",
        "automatic_full_production_authorized": False,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "atlas_job_id": plan["atlas_job_id"],
        "render_sha256": result["sha256"],
        "model": result.get("model"),
        "renderer_route": result.get("renderer_route"),
        "ledger_state": record.state,
        "visual_qa": report["visual_qa"],
        "output": str(OUTPUT_PNG),
    }, indent=2))


if __name__ == "__main__":
    main()
