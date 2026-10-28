"""Single Modal render path for World Asset Pipeline V2."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
from pathlib import Path

import modal
from PIL import Image

from modal_worker.world_asset_pipeline_v2_planner import (
    MAX_BATCH_SIZE,
    build_rows,
    paid_gate_open,
)

APP_NAME = "freeframe-world-asset-pipeline-v2"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
SOURCE_PRESET = "plushbound_tileset_source"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUTPUT_ROOT = Path("world-asset-pipeline-v2-output")
GPU_CANDIDATES = ["L4", "A10G"]
STARTUP_TIMEOUT_SECONDS = 180
REMOTE_TIMEOUT_SECONDS = 300

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "accelerate", "diffusers", "pillow>=10.4,<12", "safetensors",
        "sentencepiece", "torch>=2.6,<3", "transformers",
    )
    .add_local_python_source("modal_worker")
)
app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


@app.cls(
    gpu=GPU_CANDIDATES,
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    startup_timeout=STARTUP_TIMEOUT_SECONDS,
    timeout=REMOTE_TIMEOUT_SECONDS,
)
class WorldAssetV2Runner:
    @modal.enter()
    def load(self):
        os.environ["HF_HOME"] = CACHE_DIR
        os.environ["HF_HUB_CACHE"] = f"{CACHE_DIR}/hub"
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        print("WORLD_ASSET_V2_STARTUP=CONTAINER_STARTED", flush=True)
        print(f"WORLD_ASSET_V2_GPU_CANDIDATES={','.join(GPU_CANDIDATES)}", flush=True)
        from diffusers import DiffusionPipeline
        import torch
        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(
            MODEL_ID, torch_dtype=torch.bfloat16, cache_dir=CACHE_DIR,
            local_files_only=True,
        )
        print("WORLD_ASSET_V2_STARTUP=PIPELINE_CPU_READY", flush=True)
        self.pipe.to("cuda")
        print("WORLD_ASSET_V2_STARTUP=CUDA_READY", flush=True)

    def _render(self, request: dict) -> tuple[bytes, float]:
        generator = self.torch.Generator(device="cuda").manual_seed(int(request["seed"]))
        started = time.monotonic()
        result = self.pipe(
            prompt=str(request["prompt"]), width=384, height=384,
            guidance_scale=1.0, num_inference_steps=4, generator=generator,
        ).images[0]
        elapsed = time.monotonic() - started
        buf = io.BytesIO(); result.save(buf, format="PNG")
        return buf.getvalue(), elapsed

    @modal.method()
    def run_selected(self, rows: list[dict], region: str, accepted_ids: list[str]) -> dict:
        from modal_worker.production_inspector import asset_class_for_item, inspect_generation
        from modal_worker.production_request_builder import build_production_request
        from modal_worker.tileset_source_normalizer import (
            MAX_EDGE_DISCONTINUITY, MIN_RGB_STDDEV,
            edge_discontinuity, rgb_stddev,
        )
        from modal_worker.world_asset_pipeline_v2_normalizer import normalize_image

        if not 1 <= len(rows) <= MAX_BATCH_SIZE:
            raise RuntimeError("V2 runner requires 1..8 rows")
        requested = {row["asset_id"] for row in rows}
        if len(requested) != len(rows) or {row["region"] for row in rows} != {region}:
            raise RuntimeError("V2 runner duplicate/cross-region request")
        if requested.intersection(accepted_ids):
            raise RuntimeError("V2 runner refuses accepted IDs")

        prepared = []
        for item in rows:
            inspection_item = {**item, "preset": SOURCE_PRESET}
            if asset_class_for_item(inspection_item) != "tileset_master":
                raise RuntimeError(f"{item['asset_id']}: tileset inspection identity drifted")
            request = build_production_request(
                SOURCE_PRESET, item["prompt"], seed=int(item["seed"])
            )
            expected = {
                "model_id": MODEL_ID, "renderer_route": "flux2_klein",
                "width": 384, "height": 384, "steps": 4, "guidance_scale": 1.0,
                "bounded_production_authorized": True,
                "automatic_full_production_authorized": False,
                "catalog_wide_launch_authorized": False,
                "production_style_validated": True,
                "production_style_profile": SOURCE_PRESET,
            }
            for key, value in expected.items():
                if request.get(key) != value:
                    raise RuntimeError(f"{item['asset_id']}: invariant {key} drifted")
            prepared.append((item, request, inspection_item))

        outputs = []
        total_gpu = 0.0
        wall_started = time.monotonic()
        for item, request, inspection_item in prepared:
            base = {
                "asset_id": item["asset_id"], "material_key": item["material_key"],
                "region": region, "input_state": item["input_state"],
                "preset": SOURCE_PRESET,
                "prompt_sha256": item["prompt_sha256"], "seed": int(item["seed"]),
                "generation_attempts": 1,
            }
            raw: bytes | None = None
            raw_b64: str | None = None
            raw_sha: str | None = None
            elapsed = 0.0
            try:
                print(f"WORLD_ASSET_V2_RENDER=BEGIN:{item['asset_id']}", flush=True)
                raw, elapsed = self._render(request)
                total_gpu += elapsed
                raw_b64 = base64.b64encode(raw).decode("ascii")
                raw_sha = hashlib.sha256(raw).hexdigest()
                payload = {
                    "image_base64": raw_b64,
                    "width": 384, "height": 384, "seed": int(item["seed"]),
                }
                inspection = inspect_generation(inspection_item, payload)
                with Image.open(io.BytesIO(raw)) as generated:
                    normalized = normalize_image(generated)
                edge = edge_discontinuity(normalized); stddev = rgb_stddev(normalized)
                nbuf = io.BytesIO(); normalized.save(nbuf, format="PNG"); norm = nbuf.getvalue()
                passed = bool(inspection["accepted"]) and edge <= MAX_EDGE_DISCONTINUITY and stddev >= MIN_RGB_STDDEV
                outputs.append({
                    **base,
                    "execution_outcome": "PENDING_MANUAL_QA" if passed else "REJECTED_TECHNICAL",
                    "machine_gate": "PASS" if passed else "FAIL",
                    "manual_visual_gate": "PENDING" if passed else "NOT_RUN",
                    "normalizer_policy": "WORLD_ASSET_PIPELINE_V2",
                    "raw_inspection": inspection,
                    "edge_discontinuity": round(edge, 6), "rgb_stddev": round(stddev, 4),
                    "raw_sha256": raw_sha,
                    "normalized_sha256": hashlib.sha256(norm).hexdigest(),
                    "gpu_seconds": round(elapsed, 3),
                    "raw_png_base64": raw_b64,
                    "normalized_png_base64": base64.b64encode(norm).decode("ascii"),
                })
                print(f"WORLD_ASSET_V2_RENDER=DONE:{item['asset_id']}:{elapsed:.3f}s", flush=True)
            except Exception as exc:
                rendered = raw is not None and raw_b64 is not None and raw_sha is not None
                error_row = {
                    **base,
                    "execution_outcome": "REJECTED_TECHNICAL",
                    "machine_gate": "ERROR", "manual_visual_gate": "NOT_RUN",
                    "normalizer_policy": "WORLD_ASSET_PIPELINE_V2",
                    "failure_stage": "POST_RENDER_QA" if rendered else "RENDER",
                    "error_type": type(exc).__name__, "error_message": str(exc)[:1000],
                    "gpu_seconds": round(elapsed, 3),
                    "paid_render_preserved": bool(rendered),
                }
                if rendered:
                    error_row.update({
                        "raw_sha256": raw_sha,
                        "raw_png_base64": raw_b64,
                    })
                outputs.append(error_row)
                print(
                    f"WORLD_ASSET_V2_RENDER=ASSET_ERROR:{item['asset_id']}:{error_row['failure_stage']}:{type(exc).__name__}",
                    flush=True,
                )

        passes = sum(row["machine_gate"] == "PASS" for row in outputs)
        return {
            "schema": "plushbound.world_asset_pipeline_v2_batch_report.v1",
            "status": "COMPLETED_PER_ASSET_RESULTS", "region": region,
            "requested_count": len(rows), "generation_count": len(rows),
            "generation_retry_count": 0, "machine_pass_count": passes,
            "machine_rejected_or_error_count": len(rows) - passes,
            "accepted_ids_excluded": sorted(accepted_ids),
            "failure_isolated_to_asset_id": True,
            "paid_render_preserved_before_qa": True,
            "manual_visual_qa_required": True,
            "normalizer_policy": "WORLD_ASSET_PIPELINE_V2",
            "compile_authorized": False, "catalog_wide_launch_authorized": False,
            "runtime_import_proof": True,
            "gpu_candidates": GPU_CANDIDATES,
            "total_gpu_seconds": round(total_gpu, 3),
            "wall_seconds": round(time.monotonic() - wall_started, 3),
            "outputs": outputs,
        }


def _save(report: dict) -> dict:
    root = OUTPUT_ROOT / report["region"]; root.mkdir(parents=True, exist_ok=True)
    clean_rows = []
    for source in report["outputs"]:
        row = dict(source)
        raw64 = row.pop("raw_png_base64", None); norm64 = row.pop("normalized_png_base64", None)
        out = root / row["material_key"]; out.mkdir(parents=True, exist_ok=True)
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


@app.local_entrypoint()
def main(region: str, request_ids_json: str = ""):
    requested = json.loads(request_ids_json) if request_ids_json else None
    if requested is not None and not isinstance(requested, list):
        raise RuntimeError("request_ids_json must decode to a list")
    rows, plan = build_rows(region, requested)
    if not rows:
        raise RuntimeError(f"{region}: no generation-eligible IDs selected")
    paid_gate_open(region, requested_count=len(rows))
    report = WorldAssetV2Runner().run_selected.remote(rows, region, plan["accepted_ids_excluded"])
    clean = _save(report)
    print(json.dumps({
        "status": clean["status"], "region": region,
        "requested_count": clean["requested_count"],
        "machine_pass_count": clean["machine_pass_count"],
        "machine_rejected_or_error_count": clean["machine_rejected_or_error_count"],
        "generation_retry_count": 0, "total_gpu_seconds": clean["total_gpu_seconds"],
    }, sort_keys=True))


def declaration_validation() -> dict:
    from modal_worker.production_inspector import asset_class_for_item

    if GPU_CANDIDATES != ["L4", "A10G"]:
        raise RuntimeError("V2 GPU fallback declaration drift")
    if not 1 <= MAX_BATCH_SIZE <= 8:
        raise RuntimeError("V2 batch cap drift")
    if STARTUP_TIMEOUT_SECONDS <= 0 or REMOTE_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("V2 timeout declaration invalid")
    inspection_asset_class = asset_class_for_item({"preset": SOURCE_PRESET})
    if inspection_asset_class != "tileset_master":
        raise RuntimeError("V2 tileset inspection preset is not recognized")
    return {
        "schema": "plushbound.world_asset_pipeline_v2_runner_validation.v1",
        "status": "PASS_ZERO_GPU_SINGLE_RUNNER_DECLARATION",
        "model_id": MODEL_ID,
        "source_preset": SOURCE_PRESET,
        "inspection_asset_class": inspection_asset_class,
        "gpu_candidates": GPU_CANDIDATES,
        "startup_timeout_seconds": STARTUP_TIMEOUT_SECONDS,
        "remote_timeout_seconds": REMOTE_TIMEOUT_SECONDS,
        "max_batch_size": MAX_BATCH_SIZE,
        "normalizer_policy": "WORLD_ASSET_PIPELINE_V2",
        "failure_isolated_to_asset_id": True,
        "batch_art_rejection_does_not_abort_sibling_assets": True,
        "paid_render_preserved_before_qa": True,
        "exact_requested_count_gate_required": True,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": True,
    }
