"""Reference-aware bounded executor for World Asset Pipeline V2.

Reference sheets are visual authority only. This runner stores a verified regional
conditioning anchor, asks Vera's deployed FLUX.2/Klein production generator to
create NEW source artwork from it, and preserves provenance for later deterministic
compilation. Reference pixels are never emitted as runtime art.
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
from modal_worker.world_asset_pipeline_v2_normalizer import normalize_image
from modal_worker.world_asset_pipeline_v2_planner import (
    MAX_BATCH_SIZE,
    build_rows,
    paid_gate_open,
)

MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
RENDERER_ROUTE = "flux2_klein"
SOURCE_PRESET = "plushbound_tileset_source"
OUTPUT_ROOT = Path("world-asset-pipeline-v2-output")
CONDITIONING_PATH = Path("modal_worker/world_asset_pipeline_v2_reference_conditioning.json")


def _load_conditioning(region: str) -> tuple[dict, bytes]:
    data = json.loads(CONDITIONING_PATH.read_text(encoding="utf-8"))
    if data.get("schema") != "plushbound.world_asset_pipeline_v2_reference_conditioning.v1":
        raise RuntimeError("reference conditioning schema mismatch")
    cfg = data.get("regions", {}).get(region)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"{region}: no accepted reference-conditioning contract")
    if cfg.get("status") != "REFERENCE_AUTHORITY_ACCEPTED":
        raise RuntimeError(f"{region}: reference authority is not accepted")
    if cfg.get("required_producer") != "vera-modal":
        raise RuntimeError(f"{region}: required producer must be vera-modal")
    if cfg.get("reference_sheet_pixels_may_be_runtime_art") is not False:
        raise RuntimeError(f"{region}: reference pixels must be runtime-forbidden")
    anchor_path = Path(str(cfg.get("anchor_path", "")))
    raw = anchor_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != cfg.get("anchor_sha256"):
        raise RuntimeError(f"{region}: conditioning anchor hash mismatch")
    with Image.open(io.BytesIO(raw)) as image:
        image.verify()
    scale = float(cfg.get("reference_scale", 0.35))
    if not 0.0 < scale <= 1.0:
        raise RuntimeError(f"{region}: invalid reference scale")
    if cfg.get("reference_mode") not in {"style", "balanced"}:
        raise RuntimeError(f"{region}: invalid reference mode")
    if not str(cfg.get("conditioning_prompt_prefix", "")).strip():
        raise RuntimeError(f"{region}: conditioning prompt prefix is required")
    return cfg, raw


def _prepare(item: dict, cfg: dict, reference_id: str) -> tuple[dict, dict]:
    inspection_item = {**item, "preset": SOURCE_PRESET}
    if asset_class_for_item(inspection_item) != "tileset_master":
        raise RuntimeError(f"{item['asset_id']}: tileset inspection identity drifted")
    request = build_production_request(
        SOURCE_PRESET,
        item["prompt"],
        seed=int(item["seed"]),
    )
    expected = {
        "model_id": MODEL_ID,
        "renderer_route": RENDERER_ROUTE,
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
    request["prompt"] = (
        str(cfg["conditioning_prompt_prefix"]).strip()
        + " "
        + str(request["prompt"]).strip()
    )
    request["reference_id"] = reference_id
    request["reference_scale"] = float(cfg["reference_scale"])
    request["reference_mode"] = str(cfg["reference_mode"])
    return request, inspection_item


def _run(region: str, rows: list[dict], accepted_ids: list[str]) -> dict:
    if not 1 <= len(rows) <= MAX_BATCH_SIZE:
        raise RuntimeError("V2 reference runner requires 1..8 rows")
    requested = {row["asset_id"] for row in rows}
    if len(requested) != len(rows) or {row["region"] for row in rows} != {region}:
        raise RuntimeError("V2 reference runner duplicate/cross-region request")
    if requested.intersection(accepted_ids):
        raise RuntimeError("V2 reference runner refuses accepted IDs")

    cfg, reference_raw = _load_conditioning(region)
    reference_sha = hashlib.sha256(reference_raw).hexdigest()
    store = modal.Function.from_name("freeframe-worker", "store_reference_internal")
    stored = store.remote({"image_base64": base64.b64encode(reference_raw).decode("ascii")})
    if stored.get("stored") is not True or stored.get("reference_id") != reference_sha:
        raise RuntimeError(f"{region}: Modal reference-store verification failed")

    generator = modal.Cls.from_name("freeframe-worker", "FreeFrameProductionGenerator")()
    outputs = []
    total_gpu = 0.0
    wall_started = time.monotonic()

    for item in rows:
        base = {
            "asset_id": item["asset_id"],
            "material_key": item["material_key"],
            "region": region,
            "input_state": item["input_state"],
            "preset": SOURCE_PRESET,
            "prompt_sha256": item["prompt_sha256"],
            "seed": int(item["seed"]),
            "generation_attempts": 1,
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
            request, inspection_item = _prepare(item, cfg, reference_sha)
            print(f"WORLD_ASSET_V2_REFERENCE_RENDER=BEGIN:{item['asset_id']}", flush=True)
            result = generator.generate.remote(request)
            elapsed = float(result.get("elapsed_seconds", 0.0))
            total_gpu += elapsed
            if result.get("model") != MODEL_ID or result.get("renderer_route") != RENDERER_ROUTE:
                raise RuntimeError("Vera production renderer identity mismatch")
            reference_metadata = result.get("reference_conditioning")
            if not isinstance(reference_metadata, dict):
                raise RuntimeError("Vera result omitted reference conditioning metadata")
            if reference_metadata.get("reference_id") != reference_sha:
                raise RuntimeError("Vera result used the wrong reference anchor")
            if float(reference_metadata.get("requested_scale", -1)) != float(cfg["reference_scale"]):
                raise RuntimeError("Vera result reference scale mismatch")

            raw_b64 = str(result["image_base64"])
            raw = base64.b64decode(raw_b64, validate=True)
            raw_sha = hashlib.sha256(raw).hexdigest()
            if raw_sha != result.get("sha256"):
                raise RuntimeError("Vera generated-output hash mismatch")

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
            nbuf = io.BytesIO()
            normalized.save(nbuf, format="PNG")
            norm = nbuf.getvalue()
            passed = (
                bool(inspection["accepted"])
                and edge <= MAX_EDGE_DISCONTINUITY
                and stddev >= MIN_RGB_STDDEV
            )
            outputs.append({
                **base,
                "execution_outcome": "PENDING_MANUAL_QA" if passed else "REJECTED_TECHNICAL",
                "machine_gate": "PASS" if passed else "FAIL",
                "manual_visual_gate": "PENDING" if passed else "NOT_RUN",
                "normalizer_policy": "WORLD_ASSET_PIPELINE_V2",
                "raw_inspection": inspection,
                "edge_discontinuity": round(edge, 6),
                "rgb_stddev": round(stddev, 4),
                "raw_sha256": raw_sha,
                "normalized_sha256": hashlib.sha256(norm).hexdigest(),
                "gpu_seconds": round(elapsed, 3),
                "raw_png_base64": raw_b64,
                "normalized_png_base64": base64.b64encode(norm).decode("ascii"),
                "vera_reference_conditioning": reference_metadata,
                "source_generation_proof": {
                    "producer": "vera-modal",
                    "model_id": MODEL_ID,
                    "renderer_route": RENDERER_ROUTE,
                    "generated_output_sha256": raw_sha,
                    "reference_anchor_sha256": reference_sha,
                },
            })
            print(
                f"WORLD_ASSET_V2_REFERENCE_RENDER=DONE:{item['asset_id']}:{elapsed:.3f}s",
                flush=True,
            )
        except Exception as exc:
            rendered = raw is not None and raw_b64 is not None and raw_sha is not None
            error_row = {
                **base,
                "execution_outcome": "REJECTED_TECHNICAL",
                "machine_gate": "ERROR",
                "manual_visual_gate": "NOT_RUN",
                "normalizer_policy": "WORLD_ASSET_PIPELINE_V2",
                "failure_stage": "POST_RENDER_QA" if rendered else "RENDER",
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:1000],
                "gpu_seconds": round(elapsed, 3),
                "paid_render_preserved": bool(rendered),
            }
            if rendered:
                error_row.update({
                    "raw_sha256": raw_sha,
                    "raw_png_base64": raw_b64,
                    "source_generation_proof": {
                        "producer": "vera-modal",
                        "model_id": MODEL_ID,
                        "renderer_route": RENDERER_ROUTE,
                        "generated_output_sha256": raw_sha,
                        "reference_anchor_sha256": reference_sha,
                    },
                })
            outputs.append(error_row)
            print(
                f"WORLD_ASSET_V2_REFERENCE_RENDER=ASSET_ERROR:{item['asset_id']}:{error_row['failure_stage']}:{type(exc).__name__}",
                flush=True,
            )

    passes = sum(row["machine_gate"] == "PASS" for row in outputs)
    return {
        "schema": "plushbound.world_asset_pipeline_v2_batch_report.v2",
        "status": "COMPLETED_PER_ASSET_RESULTS",
        "region": region,
        "requested_count": len(rows),
        "generation_count": len(rows),
        "generation_retry_count": 0,
        "machine_pass_count": passes,
        "machine_rejected_or_error_count": len(rows) - passes,
        "accepted_ids_excluded": sorted(accepted_ids),
        "failure_isolated_to_asset_id": True,
        "paid_render_preserved_before_qa": True,
        "manual_visual_qa_required": True,
        "normalizer_policy": "WORLD_ASSET_PIPELINE_V2",
        "compile_authorized": False,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": True,
        "source_art_provenance": "vera-modal-generated",
        "reference_sheet_pixels_used_as_runtime_art": False,
        "reference_anchor_sha256": reference_sha,
        "total_gpu_seconds": round(total_gpu, 3),
        "wall_seconds": round(time.monotonic() - wall_started, 3),
        "outputs": outputs,
    }


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
            raw = base64.b64decode(raw64)
            path = out / f"{row['material_key']}-384.png"
            path.write_bytes(raw)
            if hashlib.sha256(raw).hexdigest() != row["raw_sha256"]:
                raise RuntimeError("raw hash mismatch")
            row["raw_path"] = str(path)
        if norm64:
            norm = base64.b64decode(norm64)
            path = out / f"{row['material_key']}-48.png"
            path.write_bytes(norm)
            if hashlib.sha256(norm).hexdigest() != row["normalized_sha256"]:
                raise RuntimeError("normalized hash mismatch")
            row["normalized_path"] = str(path)
        (out / "report.json").write_text(
            json.dumps(row, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        clean_rows.append(row)
    clean = {**report, "outputs": clean_rows}
    (root / "batch-report.json").write_text(
        json.dumps(clean, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return clean


def main(region: str, request_ids_json: str = "") -> dict:
    requested = json.loads(request_ids_json) if request_ids_json else None
    if requested is not None and not isinstance(requested, list):
        raise RuntimeError("request_ids_json must decode to a list")
    rows, plan = build_rows(region, requested)
    if not rows:
        raise RuntimeError(f"{region}: no generation-eligible IDs selected")
    paid_gate_open(region, requested_count=len(rows))
    report = _run(region, rows, plan["accepted_ids_excluded"])
    clean = _save(report)
    print(json.dumps({
        "status": clean["status"],
        "region": region,
        "requested_count": clean["requested_count"],
        "machine_pass_count": clean["machine_pass_count"],
        "machine_rejected_or_error_count": clean["machine_rejected_or_error_count"],
        "generation_retry_count": 0,
        "total_gpu_seconds": clean["total_gpu_seconds"],
        "source_art_provenance": clean["source_art_provenance"],
        "reference_anchor_sha256": clean["reference_anchor_sha256"],
    }, sort_keys=True))
    return clean


def declaration_validation() -> dict:
    data = json.loads(CONDITIONING_PATH.read_text(encoding="utf-8"))
    if data.get("schema") != "plushbound.world_asset_pipeline_v2_reference_conditioning.v1":
        raise RuntimeError("conditioning schema drift")
    if not 1 <= MAX_BATCH_SIZE <= 8:
        raise RuntimeError("V2 batch cap drift")
    for region in data.get("regions", {}):
        _load_conditioning(region)
    return {
        "schema": "plushbound.world_asset_pipeline_v2_reference_runner_validation.v1",
        "status": "PASS_ZERO_GPU_REFERENCE_AWARE_RUNNER_DECLARATION",
        "model_id": MODEL_ID,
        "renderer_route": RENDERER_ROUTE,
        "source_preset": SOURCE_PRESET,
        "max_batch_size": MAX_BATCH_SIZE,
        "failure_isolated_to_asset_id": True,
        "batch_art_rejection_does_not_abort_sibling_assets": True,
        "paid_render_preserved_before_qa": True,
        "exact_requested_count_gate_required": True,
        "reference_sheet_pixels_used_as_runtime_art": False,
        "required_source_art_provenance": "vera-modal-generated",
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": True,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--request-ids-json", default="")
    args = parser.parse_args()
    main(args.region, args.request_ids_json)
