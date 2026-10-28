"""Exact eight-source paid canary for Elyndor A5 material language.

Hard limits:
- exactly eight source masters;
- one generation attempt per source (no hidden retry spend);
- 384x384 Klein source art only;
- deterministic normalization to 48x48 after raw inspection;
- no full A5 sheet or cross-region production.
"""
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

APP_NAME = "freeframe-tileset-source-canary"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
VERSION = "plushbound-tileset-source-canary-v1-elyndor-a5"
MANIFEST_PATH = Path("modal_worker/tileset_source_canary_manifest.json")
OUTPUT_DIR = Path("tileset-source-canary")
EXPECTED_COUNT = 8
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

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "accelerate",
        "diffusers",
        "pillow>=10.4,<12",
        "safetensors",
        "sentencepiece",
        "torch>=2.6,<3",
        "transformers",
    )
    .add_local_python_source("modal_worker")
)

app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


def stable_seed(asset_id: str) -> int:
    digest = hashlib.sha256(f"{VERSION}:{asset_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def load_assets() -> list[dict]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if data["schema"] != "plushbound.tileset_source_canary.v1":
        raise RuntimeError("unexpected source canary manifest schema")
    if data["source_count"] != EXPECTED_COUNT:
        raise RuntimeError("source canary count changed")
    if data["paid_execution_authorized"] is not False:
        raise RuntimeError("manifest must remain preflight-only; paid launch authority comes from explicit workflow trigger")
    if data["region"] != "elyndor" or data["target_sheet_type"] != "A5":
        raise RuntimeError("source canary target changed")
    rows = []
    for source in data["materials"]:
        asset_id = str(source["asset_id"])
        rows.append({
            "asset_id": asset_id,
            "material_key": str(source["material_key"]),
            "region": "elyndor",
            "target_sheet_type": "A5",
            "preset": "plushbound_tileset_source",
            "asset_class": "tileset_master",
            "prompt": str(source["prompt"]),
            "seed": stable_seed(asset_id),
        })
    ids = {row["asset_id"] for row in rows}
    if len(rows) != EXPECTED_COUNT or ids != EXPECTED_IDS:
        raise RuntimeError("source canary is not the exact eight approved IDs")
    return rows


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    timeout=1200,
)
class TilesetSourceCanaryRunner:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import DiffusionPipeline

        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
            cache_dir=CACHE_DIR,
        )
        self.pipe.to("cuda")

    def _render(self, request: dict) -> tuple[bytes, float]:
        generator = self.torch.Generator(device="cuda").manual_seed(int(request["seed"]))
        started = time.monotonic()
        result = self.pipe(
            prompt=str(request["prompt"]),
            width=int(request["width"]),
            height=int(request["height"]),
            guidance_scale=float(request["guidance_scale"]),
            num_inference_steps=int(request["steps"]),
            generator=generator,
        ).images[0]
        elapsed = time.monotonic() - started
        out = io.BytesIO()
        result.save(out, format="PNG")
        return out.getvalue(), elapsed

    @modal.method()
    def run_assets(self, rows: list[dict]) -> dict:
        from modal_worker.production_inspector import inspect_generation
        from modal_worker.production_request_builder import build_production_request
        from modal_worker.tileset_source_normalizer import (
            MAX_EDGE_DISCONTINUITY,
            MIN_RGB_STDDEV,
            edge_discontinuity,
            normalize_image,
            rgb_stddev,
        )

        ids = {str(row["asset_id"]) for row in rows}
        if len(rows) != EXPECTED_COUNT or ids != EXPECTED_IDS:
            raise RuntimeError("remote canary received anything other than exact eight IDs")

        outputs = []
        total_gpu_seconds = 0.0
        wall_started = time.monotonic()
        for item in rows:
            request = build_production_request(
                "plushbound_tileset_source",
                str(item["prompt"]),
                seed=int(item["seed"]),
            )
            invariants = {
                "model_id": MODEL_ID,
                "renderer_route": "flux2_klein",
                "width": 384,
                "height": 384,
                "steps": 4,
                "guidance_scale": 1.0,
                "bounded_production_authorized": True,
                "automatic_full_production_authorized": False,
                "catalog_wide_launch_authorized": False,
                "production_style_validated": True,
                "production_style_profile": "plushbound_tileset_source",
            }
            for key, expected in invariants.items():
                if request.get(key) != expected:
                    raise RuntimeError(
                        f"{item['asset_id']}: invariant {key}={request.get(key)!r}, expected={expected!r}"
                    )

            raw, elapsed = self._render(request)
            total_gpu_seconds += elapsed
            raw_payload = {
                "image_base64": base64.b64encode(raw).decode("ascii"),
                "width": 384,
                "height": 384,
                "seed": int(request["seed"]),
            }
            inspection = inspect_generation(item, raw_payload)
            with Image.open(io.BytesIO(raw)) as generated:
                normalized = normalize_image(generated)
            edge = edge_discontinuity(normalized)
            stddev = rgb_stddev(normalized)
            norm_buf = io.BytesIO()
            normalized.save(norm_buf, format="PNG")
            norm_raw = norm_buf.getvalue()
            normalizer_accepted = edge <= MAX_EDGE_DISCONTINUITY and stddev >= MIN_RGB_STDDEV
            accepted = bool(inspection["accepted"]) and normalizer_accepted
            outputs.append({
                "asset_id": item["asset_id"],
                "material_key": item["material_key"],
                "region": "elyndor",
                "target_sheet_type": "A5",
                "preset": "plushbound_tileset_source",
                "model_id": MODEL_ID,
                "renderer_route": "flux2_klein",
                "generation_attempts": 1,
                "seed": int(request["seed"]),
                "source_width": 384,
                "source_height": 384,
                "normalized_width": 48,
                "normalized_height": 48,
                "elapsed_seconds": round(elapsed, 3),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "normalized_sha256": hashlib.sha256(norm_raw).hexdigest(),
                "raw_inspection": inspection,
                "edge_discontinuity": round(edge, 6),
                "maximum_edge_discontinuity": MAX_EDGE_DISCONTINUITY,
                "rgb_stddev": round(stddev, 4),
                "minimum_rgb_stddev": MIN_RGB_STDDEV,
                "normalizer_accepted": normalizer_accepted,
                "accepted": accepted,
                "quarantined": not accepted,
                "raw_png_base64": raw_payload["image_base64"],
                "normalized_png_base64": base64.b64encode(norm_raw).decode("ascii"),
            })

        accepted_count = sum(1 for row in outputs if row["accepted"])
        return {
            "schema": "plushbound.tileset_source_canary_report.v1",
            "version": VERSION,
            "requested_count": EXPECTED_COUNT,
            "generation_count": EXPECTED_COUNT,
            "generation_retry_count": 0,
            "accepted_count": accepted_count,
            "quarantined_count": EXPECTED_COUNT - accepted_count,
            "total_gpu_seconds": round(total_gpu_seconds, 3),
            "wall_seconds": round(time.monotonic() - wall_started, 3),
            "model": MODEL_ID,
            "gpu": "L4",
            "bounded_production_authorized": True,
            "automatic_full_production_authorized": False,
            "catalog_wide_launch_authorized": False,
            "full_A5_expansion_authorized": False,
            "manual_visual_qa_required": True,
            "outputs": outputs,
        }


@app.local_entrypoint()
def main():
    report = TilesetSourceCanaryRunner().run_assets.remote(load_assets())
    raw_dir = OUTPUT_DIR / "raw"
    norm_dir = OUTPUT_DIR / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    norm_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for item in report.pop("outputs"):
        raw = base64.b64decode(item.pop("raw_png_base64"))
        normalized = base64.b64decode(item.pop("normalized_png_base64"))
        if hashlib.sha256(raw).hexdigest() != item["raw_sha256"]:
            raise RuntimeError(f"{item['asset_id']}: raw artifact hash mismatch")
        if hashlib.sha256(normalized).hexdigest() != item["normalized_sha256"]:
            raise RuntimeError(f"{item['asset_id']}: normalized artifact hash mismatch")
        raw_path = raw_dir / f"{item['material_key']}-384.png"
        norm_path = norm_dir / f"{item['material_key']}-48.png"
        raw_path.write_bytes(raw)
        norm_path.write_bytes(normalized)
        item["raw_path"] = str(raw_path)
        item["normalized_path"] = str(norm_path)
        manifest.append(item)
    report["assets"] = manifest
    (OUTPUT_DIR / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "assets"}, sort_keys=True))
    if report["generation_count"] != EXPECTED_COUNT or report["generation_retry_count"] != 0:
        raise RuntimeError("tileset source canary generation count violated hard cap")
    if report["accepted_count"] != EXPECTED_COUNT or report["quarantined_count"] != 0:
        raise RuntimeError("tileset source canary failed deterministic raw/normalization gate")
