"""Bounded Chris Bourn canonical identity canary.

Atlas owns the production brief. Vera/FreeFrame owns visual generation. The proven
Chris reference is stored in the production reference volume by content hash, then
used once for a bounded FLUX.2 Klein identity-preservation render. This canary never
authorizes catalog-wide canonical production by itself.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import modal

from modal_worker.atlas_controller import plan_asset

CANARY_VERSION = "chris-canonical-identity-v1"
REFERENCE_PATH = Path("modal_worker/project_references/chris_proven_reference.jpg")
OUTPUT_DIR = Path("chris-identity-canary")
OUTPUT_PNG = OUTPUT_DIR / "chris-identity-canary.png"
REPORT_JSON = OUTPUT_DIR / "report.json"
REFERENCE_SCALE = 0.72
SEED = 2183301
EXPECTED_MODEL = "black-forest-labs/FLUX.2-klein-4B"
EXPECTED_ROUTE = "flux2_klein"


def main() -> None:
    if not REFERENCE_PATH.is_file():
        raise RuntimeError(f"missing proven Chris reference: {REFERENCE_PATH}")

    reference_raw = REFERENCE_PATH.read_bytes()
    reference_sha = hashlib.sha256(reference_raw).hexdigest()

    intent = {
        "family": "character_master",
        "description": (
            "Chris Bourn, established Plushbound Legends canonical adult male, age 33, 5 feet 5 inches tall; "
            "preserve the supplied reference identity exactly: tousled medium brown hair, bright blue eyes, youthful adult facial structure, "
            "red scarf and cape accents, layered black and deep-red fantasy travel armor with leather straps, belts, gloves and metal guards; "
            "one complete full-body three-quarter standing character illustration, head to boots visible, natural relaxed heroic posture; "
            "same person and same established outfit language as the reference, not a redesign, no extra people, no alternate views"
        ),
        "seed": SEED,
    }
    plan = plan_asset(intent)
    request = dict(plan.get("generation_request") or {})
    if not plan.get("generation_supported") or not request:
        raise RuntimeError("Atlas did not produce a generation-ready canonical request")

    # Keep the identity canary bounded and inexpensive while preserving the exact
    # production renderer/model selected by Atlas.
    request["steps"] = 8
    request["guidance_scale"] = 1.0

    store = modal.Function.from_name("freeframe-worker", "store_reference_internal")
    stored = store.remote({"image_base64": base64.b64encode(reference_raw).decode("ascii")})
    if not stored.get("stored"):
        raise RuntimeError(f"reference store failed: {stored}")
    if stored.get("reference_id") != reference_sha:
        raise RuntimeError("stored reference id does not match local reference SHA-256")

    request["reference_id"] = reference_sha
    request["reference_mode"] = "identity"
    request["reference_scale"] = REFERENCE_SCALE

    gateway = modal.Function.from_name("freeframe-worker", "generate_image_internal")
    result = gateway.remote(request)
    encoded = result.get("image_base64")
    if not encoded:
        raise RuntimeError("production gateway returned no image_base64")
    raw = base64.b64decode(encoded, validate=True)
    output_sha = hashlib.sha256(raw).hexdigest()

    ref_meta = result.get("reference_conditioning") or {}
    checks = {
        "png_signature_valid": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "nonempty_image": len(raw) > 1024,
        "output_sha_matches": result.get("sha256") == output_sha,
        "seed_matches": int(result.get("seed", -1)) == SEED,
        "model_matches": result.get("model") == EXPECTED_MODEL,
        "route_matches": result.get("renderer_route") == EXPECTED_ROUTE,
        "bounded_production": result.get("bounded_production") is True,
        "catalog_wide_still_locked": result.get("automatic_full_production_authorized") is False,
        "reference_id_matches": ref_meta.get("reference_id") == reference_sha,
        "reference_mode_identity": ref_meta.get("reference_mode") == "identity",
        "reference_scale_matches": abs(float(ref_meta.get("requested_scale", -1)) - REFERENCE_SCALE) < 1e-9,
        "atlas_visual_generation_owner_is_vera": plan.get("visual_generation_owned_by") == "Vera",
    }
    if not all(checks.values()):
        raise RuntimeError(f"Chris identity canary structural checks failed: {checks}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_PNG.write_bytes(raw)
    (OUTPUT_DIR / "chris-proven-reference.jpg").write_bytes(reference_raw)

    report = {
        "canary_version": CANARY_VERSION,
        "status": "generated_pending_identity_visual_review",
        "production_authorized": False,
        "reference": {
            "path": str(REFERENCE_PATH),
            "sha256": reference_sha,
            "bytes": len(reference_raw),
            "stored": stored,
            "mode": "identity",
            "scale": REFERENCE_SCALE,
        },
        "atlas": {
            "assistant_name": plan.get("assistant_name"),
            "controller_version": plan.get("controller_version"),
            "atlas_job_id": plan.get("atlas_job_id"),
            "plan_digest": plan.get("plan_digest"),
            "visual_generation_owned_by": plan.get("visual_generation_owned_by"),
            "responsibility_boundary": plan.get("responsibility_boundary"),
        },
        "generation": {
            "request": request,
            "result_metadata": {k: v for k, v in result.items() if k != "image_base64"},
            "output_sha256": output_sha,
            "checks": checks,
        },
        "identity_visual_qa": "pending_human_review",
        "automatic_full_production_authorized": False,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "reference_id": reference_sha,
        "output_sha256": output_sha,
        "model": result.get("model"),
        "renderer_route": result.get("renderer_route"),
        "identity_visual_qa": report["identity_visual_qa"],
    }, indent=2))


if __name__ == "__main__":
    main()
