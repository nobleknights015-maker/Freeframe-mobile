"""Corrected reference-aware paid batch controller for current-chat regional repair.

This controller is deliberately narrow. It may generate only source IDs explicitly
listed in world_asset_pipeline_v2_provenance_repair.json, uses the dedicated Vera
FLUX.2 Klein reference worker, keeps compile disabled, and preserves old accepted
bytes when a provenance-repair supersession is authorized.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import time
from pathlib import Path

import modal
from PIL import Image

from modal_worker.production_inspector import asset_class_for_item, inspect_generation
from modal_worker.production_request_builder import build_production_request
from modal_worker.tileset_source_normalizer import (
    MAX_EDGE_DISCONTINUITY,
    MIN_RGB_STDDEV,
    edge_discontinuity,
    rgb_stddev,
)
from modal_worker.world_asset_pipeline_v2_controller import resolve_state
from modal_worker.world_asset_pipeline_v2_normalizer import normalize_image
from modal_worker.world_asset_pipeline_v2_planner import (
    MAX_BATCH_SIZE,
    PROMPT_CONTRACT_VERSION,
    _seed,
    validate_receiver_contract,
)

# Keep these duplicated here so the repaired lane cannot silently drift with a legacy renderer.
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
RENDERER_ROUTE = "flux2_klein_reference_v2"
SOURCE_PRESET = "plushbound_tileset_source"
WORKER_APP = "freeframe-flux2-reference-worker"
WORKER_CLASS = "VeraFlux2ReferenceGenerator"
OUTPUT_ROOT = Path("world-asset-pipeline-v2-output")
CONDITIONING_PATH = Path("modal_worker/world_asset_pipeline_v2_reference_conditioning.json")
REPAIR_PATH = Path("modal_worker/world_asset_pipeline_v2_provenance_repair.json")
AUTH_PATH = Path("modal_worker/world_asset_pipeline_v2_paid_authorization.json")
SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
STATE_PATH = Path("modal_worker/world_asset_pipeline_v2_state.json")
FREEZE_PATH = Path("modal_worker/world_asset_pipeline_v2_freeze.json")
VALIDATED_REFERENCE_WORKER_PREFLIGHT_RUN_ID = 40789252831


def _load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing required V2 input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _conditioning(region: str) -> tuple[dict, bytes]:
    data = _load(CONDITIONING_PATH)
    if data.get("schema") != "plushbound.world_asset_pipeline_v2_reference_conditioning.v1":
        raise RuntimeError("reference conditioning schema mismatch")
    cfg = data.get("regions", {}).get(region)
    if not isinstance(cfg, dict) or cfg.get("status") != "REFERENCE_AUTHORITY_ACCEPTED":
        raise RuntimeError(f"{region}: accepted reference authority is missing")
    if cfg.get("required_producer") != "vera-modal":
        raise RuntimeError(f"{region}: producer must be vera-modal")
    if cfg.get("reference_sheet_pixels_may_be_runtime_art") is not False:
        raise RuntimeError(f"{region}: reference pixels are not runtime-forbidden")
    path = Path(str(cfg.get("anchor_path", "")))
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != cfg.get("anchor_sha256"):
        raise RuntimeError(f"{region}: conditioning anchor hash mismatch")
    with Image.open(io.BytesIO(raw)) as image:
        image.verify()
    return cfg, raw


def _repair_scope(region: str) -> dict:
    repair = _load(REPAIR_PATH)
    if repair.get("schema") != "plushbound.world_asset_pipeline_v2_provenance_repair.v1":
        raise RuntimeError("provenance repair schema mismatch")
    if repair.get("status") != "AUTHORIZED_CURRENT_CHAT_REPAIR_ONLY":
        raise RuntimeError("current-chat repair scope is not authorized")
    if repair.get("required_source_art_provenance") != "vera-modal-generated":
        raise RuntimeError("repair provenance requirement drifted")
    if repair.get("reference_sheet_pixels_used_as_runtime_art") is not False:
        raise RuntimeError("repair scope permits reference runtime pixels")
    if repair.get("compile_authorized") is not False or repair.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("repair scope is too broad")
    regional = repair.get("regions", {}).get(region)
    if not isinstance(regional, dict):
        raise RuntimeError(f"{region}: not authorized by current-chat repair scope")
    return regional


def build_repair_rows(region: str, requested_ids: list[str]) -> tuple[list[dict], list[str]]:
    if not isinstance(requested_ids, list) or not 1 <= len(requested_ids) <= MAX_BATCH_SIZE:
        raise RuntimeError("requested_ids must contain 1..8 source IDs")
    if len(requested_ids) != len(set(requested_ids)):
        raise RuntimeError("requested_ids contains duplicates")

    repair = _repair_scope(region)
    allowed = set(repair.get("source_ids", []))
    superseded = set(repair.get("superseded_accepted_ids", []))
    if not set(requested_ids).issubset(allowed):
        raise RuntimeError("requested source ID is outside current-chat repair scope")

    scope = _load(SCOPE_PATH)
    source = scope.get("source_contract", {})
    regional = scope.get("regions", {}).get(region)
    if not isinstance(regional, dict):
        raise RuntimeError(f"{region}: missing regional A5 scope")
    materials = list(regional.get("materials", []))
    labels = regional.get("material_prompt_labels", {})
    if len(materials) != 8 or set(labels) != set(materials):
        raise RuntimeError(f"{region}: invalid eight-material scope")
    if source.get("prompt_contract_version") != PROMPT_CONTRACT_VERSION:
        raise RuntimeError("prompt contract drift")
    required = [str(x).lower() for x in source.get("required_prompt_phrases", [])]
    resolved = resolve_state()["regions"][region]

    rows = []
    prefix = f"tileset.{region}.a5.source."
    for asset_id in requested_ids:
        if not asset_id.startswith(prefix):
            raise RuntimeError(f"{asset_id}: stable source ID mismatch")
        material = asset_id[len(prefix):]
        if material not in materials:
            raise RuntimeError(f"{asset_id}: material is outside region scope")
        state = resolved["assets"][asset_id]
        if state.get("state") == "ACCEPTED" and asset_id not in superseded:
            raise RuntimeError(f"{asset_id}: accepted asset is immutable and not superseded")
        prompt = source["prompt_template"].format(
            region_material_hint=str(regional["region_material_hint"]),
            material_name=str(labels[material]),
        )
        if state.get("prompt_suffix"):
            prompt += " " + str(state["prompt_suffix"]).strip()
        if not all(term in prompt.lower() for term in required):
            raise RuntimeError(f"{asset_id}: anti-scene prompt contract incomplete")
        prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        rows.append({
            "asset_id": asset_id,
            "material_key": material,
            "region": region,
            "input_state": "ACCEPTED_SUPERSEDED_PROVENANCE_REPAIR" if asset_id in superseded else state["state"],
            "prompt": prompt,
            "prompt_sha256": prompt_sha,
            "prompt_contract_version": PROMPT_CONTRACT_VERSION,
            "seed": _seed(asset_id, prompt_sha),
            "supersedes_historical_acceptance": asset_id in superseded,
        })
    return rows, sorted(superseded.intersection(requested_ids))


def validate_paid_authorization(region: str, requested_count: int) -> dict:
    auth = _load(AUTH_PATH)
    state = _load(STATE_PATH)
    freeze = _load(FREEZE_PATH)
    if auth.get("schema") != "plushbound.world_asset_pipeline_v2_paid_authorization.v1":
        raise RuntimeError("paid authorization schema mismatch")
    if auth.get("enabled") is not True or auth.get("region") != region:
        raise RuntimeError("paid authorization is disabled or bound to another region")
    limits = [auth.get("provider_calls_allowed"), auth.get("gpu_calls_allowed"), auth.get("generation_calls_allowed")]
    if any(not isinstance(v, int) or isinstance(v, bool) for v in limits):
        raise RuntimeError("paid authorization call caps must be integers")
    if len(set(limits)) != 1 or limits[0] != requested_count:
        raise RuntimeError("paid authorization call caps must equal exact requested count")
    if auth.get("reference_aware_runner_required") is not True:
        raise RuntimeError("reference-aware runner is not required")
    if auth.get("required_source_art_provenance") != "vera-modal-generated":
        raise RuntimeError("authorization provenance drift")
    if auth.get("reference_sheet_pixels_used_as_runtime_art") is not False:
        raise RuntimeError("authorization permits reference runtime pixels")
    if auth.get("manual_visual_qa_required") is not True:
        raise RuntimeError("manual visual QA must remain required")
    if auth.get("compile_authorized") is not False or auth.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("authorization is too broad")
    if int(auth.get("validated_reference_preflight_run_id", 0)) != VALIDATED_REFERENCE_WORKER_PREFLIGHT_RUN_ID:
        raise RuntimeError("authorization is not pinned to the dedicated FLUX2 reference-worker preflight")
    if freeze.get("accepted_assets_immutable") is not True:
        raise RuntimeError("accepted-asset immutability protection missing")
    if freeze.get("missing_local_artifact_is_not_rerender_authority") is not True:
        raise RuntimeError("missing-artifact protection missing")
    if state.get("catalog_wide_launch_authorized") is not False or freeze.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("catalog-wide launch must remain disabled")
    receiver = validate_receiver_contract(state_data=state, freeze_data=freeze)
    return {
        "status": "PASS_FLUX2_REFERENCE_REPAIR_AUTHORIZATION",
        "region": region,
        "authorized_call_cap": requested_count,
        "receiver_contract_status": receiver["status"],
    }


def _prepare_request(item: dict, cfg: dict, reference_id: str) -> tuple[dict, dict]:
    inspection_item = {**item, "preset": SOURCE_PRESET}
    if asset_class_for_item(inspection_item) != "tileset_master":
        raise RuntimeError(f"{item['asset_id']}: inspection identity drift")
    request = build_production_request(SOURCE_PRESET, item["prompt"], seed=int(item["seed"]))
    expected = {
        "model_id": MODEL_ID,
        "width": 384,
        "height": 384,
        "steps": 4,
        "guidance_scale": 1.0,
        "bounded_production_authorized": True,
        "automatic_full_production_authorized": False,
        "catalog_wide_launch_authorized": False,
        "production_style_validated": True,
        "production_style_profile": SOURCE_PRESET,
    }
    for key, value in expected.items():
        if request.get(key) != value:
            raise RuntimeError(f"{item['asset_id']}: invariant {key} drifted")
    request["renderer_route"] = RENDERER_ROUTE
    request["prompt"] = str(cfg["conditioning_prompt_prefix"]).strip() + " " + str(request["prompt"]).strip()
    request["reference_id"] = reference_id
    request["reference_sheet_pixels_used_as_runtime_art"] = False
    return request, inspection_item


def run(region: str, requested_ids: list[str]) -> dict:
    rows, superseded = build_repair_rows(region, requested_ids)
    validate_paid_authorization(region, len(rows))
    cfg, reference_raw = _conditioning(region)
    reference_sha = hashlib.sha256(reference_raw).hexdigest()

    store = modal.Function.from_name(WORKER_APP, "store_reference_internal")
    stored = store.remote({
        "image_base64": base64.b64encode(reference_raw).decode("ascii"),
        "expected_sha256": reference_sha,
    })
    if stored.get("stored") is not True or stored.get("reference_id") != reference_sha:
        raise RuntimeError(f"{region}: reference anchor store verification failed")

    generator = modal.Cls.from_name(WORKER_APP, WORKER_CLASS)()
    outputs = []
    total_gpu = 0.0
    wall_started = time.monotonic()
    for item in rows:
        base = {
            "asset_id": item["asset_id"],
            "material_key": item["material_key"],
            "region": region,
            "input_state": item["input_state"],
            "prompt_sha256": item["prompt_sha256"],
            "seed": int(item["seed"]),
            "generation_attempts": 1,
            "supersedes_historical_acceptance": bool(item["supersedes_historical_acceptance"]),
            "source_art_provenance": "vera-modal-generated",
            "reference_sheet_pixels_used_as_runtime_art": False,
            "reference_conditioning_anchor_sha256": reference_sha,
            "reference_conditioning_role": cfg["reference_role"],
            "source_reference_hashes": cfg["source_reference_hashes"],
        }
        raw = None
        raw_b64 = None
        raw_sha = None
        elapsed = 0.0
        try:
            request, inspection_item = _prepare_request(item, cfg, reference_sha)
            print(f"WORLD_ASSET_V2_FLUX2_REFERENCE_RENDER=BEGIN:{item['asset_id']}", flush=True)
            result = generator.generate.remote(request)
            elapsed = float(result.get("elapsed_seconds", 0.0))
            total_gpu += elapsed
            if result.get("model") != MODEL_ID or result.get("renderer_route") != RENDERER_ROUTE:
                raise RuntimeError("dedicated Vera renderer identity mismatch")
            if result.get("source_art_provenance") != "vera-modal-generated":
                raise RuntimeError("Vera result provenance mismatch")
            if result.get("reference_sheet_pixels_used_as_runtime_art") is not False:
                raise RuntimeError("Vera result permits reference runtime pixels")
            refmeta = result.get("reference_conditioning")
            if not isinstance(refmeta, dict) or refmeta.get("reference_id") != reference_sha:
                raise RuntimeError("Vera result reference anchor mismatch")
            raw_b64 = str(result["image_base64"])
            raw = base64.b64decode(raw_b64, validate=True)
            raw_sha = hashlib.sha256(raw).hexdigest()
            if raw_sha != result.get("sha256"):
                raise RuntimeError("generated-output hash mismatch")
            payload = {
                "image_base64": raw_b64,
                "width": int(result["width"]),
                "height": int(result["height"]),
                "seed": int(item["seed"]),
            }
            inspection = inspect_generation(inspection_item, payload)
            with Image.open(io.BytesIO(raw)) as generated:
                normalized = normalize_image(generated)
            edge = edge_discontinuity(normalized)
            stddev = rgb_stddev(normalized)
            nbuf = io.BytesIO(); normalized.save(nbuf, format="PNG"); norm = nbuf.getvalue()
            passed = bool(inspection["accepted"]) and edge <= MAX_EDGE_DISCONTINUITY and stddev >= MIN_RGB_STDDEV
            outputs.append({
                **base,
                "execution_outcome": "PENDING_MANUAL_QA" if passed else "REJECTED_TECHNICAL",
                "machine_gate": "PASS" if passed else "FAIL",
                "manual_visual_gate": "PENDING" if passed else "NOT_RUN",
                "raw_inspection": inspection,
                "edge_discontinuity": round(edge, 6),
                "rgb_stddev": round(stddev, 4),
                "raw_sha256": raw_sha,
                "normalized_sha256": hashlib.sha256(norm).hexdigest(),
                "gpu_seconds": round(elapsed, 3),
                "raw_png_base64": raw_b64,
                "normalized_png_base64": base64.b64encode(norm).decode("ascii"),
                "vera_reference_conditioning": refmeta,
                "source_generation_proof": {
                    "producer": "vera-modal",
                    "model_id": MODEL_ID,
                    "renderer_route": RENDERER_ROUTE,
                    "generated_output_sha256": raw_sha,
                    "reference_anchor_sha256": reference_sha,
                },
            })
            print(f"WORLD_ASSET_V2_FLUX2_REFERENCE_RENDER=DONE:{item['asset_id']}:{elapsed:.3f}s", flush=True)
        except Exception as exc:
            rendered = raw is not None and raw_b64 is not None and raw_sha is not None
            error = {
                **base,
                "execution_outcome": "REJECTED_TECHNICAL",
                "machine_gate": "ERROR",
                "manual_visual_gate": "NOT_RUN",
                "failure_stage": "POST_RENDER_QA" if rendered else "RENDER",
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:1000],
                "gpu_seconds": round(elapsed, 3),
                "paid_render_preserved": bool(rendered),
            }
            if rendered:
                error.update({"raw_sha256": raw_sha, "raw_png_base64": raw_b64})
            outputs.append(error)
            print(f"WORLD_ASSET_V2_FLUX2_REFERENCE_RENDER=ASSET_ERROR:{item['asset_id']}:{error['failure_stage']}:{type(exc).__name__}", flush=True)

    passes = sum(row["machine_gate"] == "PASS" for row in outputs)
    report = {
        "schema": "plushbound.world_asset_pipeline_v2_flux2_reference_batch_report.v1",
        "status": "COMPLETED_PER_ASSET_RESULTS",
        "region": region,
        "requested_count": len(rows),
        "generation_count": len(rows),
        "generation_retry_count": 0,
        "machine_pass_count": passes,
        "machine_rejected_or_error_count": len(rows) - passes,
        "superseded_historical_acceptance_ids": superseded,
        "failure_isolated_to_asset_id": True,
        "manual_visual_qa_required": True,
        "compile_authorized": False,
        "catalog_wide_launch_authorized": False,
        "source_art_provenance": "vera-modal-generated",
        "reference_sheet_pixels_used_as_runtime_art": False,
        "reference_anchor_sha256": reference_sha,
        "total_gpu_seconds": round(total_gpu, 3),
        "wall_seconds": round(time.monotonic() - wall_started, 3),
        "outputs": outputs,
    }
    return _save(report)


def _save(report: dict) -> dict:
    root = OUTPUT_ROOT / report["region"]
    root.mkdir(parents=True, exist_ok=True)
    clean_rows = []
    for source in report["outputs"]:
        row = dict(source)
        raw64 = row.pop("raw_png_base64", None)
        norm64 = row.pop("normalized_png_base64", None)
        out = root / row["material_key"]
        out.mkdir(parents=True, exist_ok=True)
        if raw64:
            raw = base64.b64decode(raw64); path = out / f"{row['material_key']}-384.png"; path.write_bytes(raw)
            if hashlib.sha256(raw).hexdigest() != row["raw_sha256"]: raise RuntimeError("raw hash mismatch")
            row["raw_path"] = str(path)
        if norm64:
            norm = base64.b64decode(norm64); path = out / f"{row['material_key']}-48.png"; path.write_bytes(norm)
            if hashlib.sha256(norm).hexdigest() != row["normalized_sha256"]: raise RuntimeError("normalized hash mismatch")
            row["normalized_path"] = str(path)
        (out / "report.json").write_text(json.dumps(row, indent=2, sort_keys=True), encoding="utf-8")
        clean_rows.append(row)
    clean = {**report, "outputs": clean_rows}
    (root / "batch-report.json").write_text(json.dumps(clean, indent=2, sort_keys=True), encoding="utf-8")
    return clean


def declaration_validation() -> dict:
    _repair_scope("tideglass-coast")
    _repair_scope("crownweave")
    _conditioning("tideglass-coast")
    _conditioning("crownweave")
    return {
        "schema": "plushbound.world_asset_pipeline_v2_flux2_reference_batch_validation.v1",
        "status": "PASS_ZERO_GPU_CORRECTED_REFERENCE_REPAIR_DECLARATION",
        "model_id": MODEL_ID,
        "renderer_route": RENDERER_ROUTE,
        "worker_app": WORKER_APP,
        "worker_class": WORKER_CLASS,
        "max_batch_size": MAX_BATCH_SIZE,
        "required_source_art_provenance": "vera-modal-generated",
        "reference_sheet_pixels_used_as_runtime_art": False,
        "compile_authorized": False,
        "catalog_wide_launch_authorized": False,
        "validated_reference_worker_preflight_run_id": VALIDATED_REFERENCE_WORKER_PREFLIGHT_RUN_ID,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--request-ids-json", required=True)
    args = parser.parse_args()
    ids = json.loads(args.request_ids_json)
    clean = run(args.region, ids)
    print(json.dumps({
        "status": clean["status"],
        "region": clean["region"],
        "requested_count": clean["requested_count"],
        "machine_pass_count": clean["machine_pass_count"],
        "machine_rejected_or_error_count": clean["machine_rejected_or_error_count"],
        "total_gpu_seconds": clean["total_gpu_seconds"],
        "source_art_provenance": clean["source_art_provenance"],
        "reference_sheet_pixels_used_as_runtime_art": clean["reference_sheet_pixels_used_as_runtime_art"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
