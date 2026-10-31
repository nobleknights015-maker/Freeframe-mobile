"""Bounded Chris Bourn 288x384 canonical portrait identity canary."""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

import modal
from PIL import Image

from modal_worker.atlas_controller import plan_asset

CANARY_VERSION = "chris-canonical-portrait-identity-v3"
REFERENCE_PATH = Path("modal_worker/project_references/chris_proven_reference.jpg")
OUTPUT_DIR = Path("chris-portrait-canary")
OUTPUT_PNG = OUTPUT_DIR / "chris-bourn-portrait.png"
REPORT_JSON = OUTPUT_DIR / "report.json"
REFERENCE_SCALE = 0.72
SEED = 2183301
WIDTH, HEIGHT = 288, 384
EXPECTED_MODEL = "black-forest-labs/FLUX.2-klein-4B"
EXPECTED_ROUTE = "flux2_klein"


def _load_reference() -> tuple[bytes, dict]:
    if not REFERENCE_PATH.is_file():
        raise RuntimeError(f"missing proven Chris reference image: {REFERENCE_PATH}")
    raw = REFERENCE_PATH.read_bytes()
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            info = {"format": image.format, "width": image.width, "height": image.height, "mode": image.mode}
    except Exception as exc:
        raise RuntimeError(f"canonical reference is not a readable raster image: {exc}") from exc
    if info["width"] < 96 or info["height"] < 160:
        raise RuntimeError(f"canonical reference is too small: {info['width']}x{info['height']}")
    return raw, info


def main() -> None:
    reference_raw, reference_info = _load_reference()
    reference_sha = hashlib.sha256(reference_raw).hexdigest()
    intent = {
        "family": "character_master",
        "description": (
            "Chris Bourn, established Plushbound Legends canonical adult male, age 33; preserve the supplied reference identity exactly: tousled medium brown hair, bright blue eyes, youthful adult facial structure, red scarf/cape accents, layered black and deep-red fantasy travel armor with leather straps and metal guards. Create one polished JRPG character portrait from chest or waist upward, centered and readable at game UI size, natural anatomy, normal hands if visible, same person and outfit language, no redesign, no text, no labels, no contact sheet, no duplicate person. MV-cover/Trinity-inspired Plushbound original illustration quality with a simple unobtrusive neutral backdrop."
        ),
        "seed": SEED,
    }
    plan = plan_asset(intent)
    request = dict(plan.get("generation_request") or {})
    if not plan.get("generation_supported") or not request:
        raise RuntimeError("Atlas did not produce a generation-ready canonical request")
    request.update({"width": WIDTH, "height": HEIGHT, "steps": 8, "guidance_scale": 1.0})

    store = modal.Function.from_name("freeframe-worker", "store_reference_internal")
    stored = store.remote({"image_base64": base64.b64encode(reference_raw).decode("ascii")})
    if not stored.get("stored") or stored.get("reference_id") != reference_sha:
        raise RuntimeError(f"reference store failed or hash mismatched: {stored}")
    request.update({"reference_id": reference_sha, "reference_mode": "identity", "reference_scale": REFERENCE_SCALE})

    gateway = modal.Function.from_name("freeframe-worker", "generate_image_internal")
    result = gateway.remote(request)
    encoded = result.get("image_base64")
    if not encoded:
        raise RuntimeError("production gateway returned no image_base64")
    raw = base64.b64decode(encoded, validate=True)
    output_sha = hashlib.sha256(raw).hexdigest()
    with Image.open(io.BytesIO(raw)) as image:
        rendered_size, rendered_format = image.size, image.format

    ref_meta = result.get("reference_conditioning") or {}
    checks = {
        "png_signature_valid": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "nonempty_image": len(raw) > 1024,
        "output_sha_matches": result.get("sha256") == output_sha,
        "dimensions_match": rendered_size == (WIDTH, HEIGHT),
        "format_png": rendered_format == "PNG",
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
        raise RuntimeError(f"Chris portrait canary structural checks failed: {checks}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_PNG.write_bytes(raw)
    (OUTPUT_DIR / "chris-proven-reference.jpg").write_bytes(reference_raw)
    report = {
        "canary_version": CANARY_VERSION,
        "status": "generated_pending_identity_visual_review",
        "production_authorized": False,
        "runtime_contract": {"width": WIDTH, "height": HEIGHT, "layout": "single_portrait"},
        "reference": {"source": str(REFERENCE_PATH), "sha256": reference_sha, "bytes": len(reference_raw), "raster": reference_info, "stored": stored, "mode": "identity", "scale": REFERENCE_SCALE},
        "atlas": {"assistant_name": plan.get("assistant_name"), "controller_version": plan.get("controller_version"), "atlas_job_id": plan.get("atlas_job_id"), "plan_digest": plan.get("plan_digest"), "visual_generation_owned_by": plan.get("visual_generation_owned_by"), "responsibility_boundary": plan.get("responsibility_boundary")},
        "generation": {"request": request, "result_metadata": {k: v for k, v in result.items() if k != "image_base64"}, "output_sha256": output_sha, "checks": checks},
        "identity_visual_qa": "pending_human_review",
        "automatic_full_production_authorized": False,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"status": report["status"], "reference_id": reference_sha, "output_sha256": output_sha, "dimensions": list(rendered_size), "model": result.get("model"), "renderer_route": result.get("renderer_route")}, indent=2))


if __name__ == "__main__":
    main()
