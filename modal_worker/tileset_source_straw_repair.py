"""Targeted one-asset repair for the quarantined Elyndor A5 straw-thatch source.

Hard limits:
- exact asset ID only;
- one generation attempt;
- 384x384 Klein source art;
- deterministic normalization to 48x48;
- no accepted-source rerenders and no A5 expansion.
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

APP_NAME = "freeframe-tileset-straw-repair"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
VERSION = "plushbound-tileset-source-straw-repair-v1"
ASSET_ID = "tileset.elyndor.a5.source.straw_thatch"
OUTPUT_DIR = Path("tileset-source-straw-repair")
PROMPT = (
    "Elyndor handcrafted fantasy roof-thatch material viewed straight down, dense overlapping dry straw fibers with clearly visible "
    "natural tonal variation across pale gold, warm amber, tan and muted brown strands, fine alternating highlights and soft fiber shadows, "
    "rich enough local value variation to remain readable when reduced to a 48 pixel RPG tileset material. Continuous material only, "
    "no bundles, no knots, no objects, no letters, no symbols, no emblems, no borders, no flat uniform color field."
)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "accelerate", "diffusers", "pillow>=10.4,<12", "safetensors", "sentencepiece",
        "torch>=2.6,<3", "transformers",
    )
    .add_local_python_source("modal_worker")
)
app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


def stable_seed() -> int:
    digest = hashlib.sha256(f"{VERSION}:{ASSET_ID}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=120, timeout=1200)
class StrawRepairRunner:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import DiffusionPipeline
        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16, cache_dir=CACHE_DIR)
        self.pipe.to("cuda")

    @modal.method()
    def run(self) -> dict:
        from modal_worker.production_inspector import inspect_generation
        from modal_worker.production_request_builder import build_production_request
        from modal_worker.tileset_source_normalizer import (
            MAX_EDGE_DISCONTINUITY, MIN_RGB_STDDEV, edge_discontinuity, normalize_image, rgb_stddev,
        )

        seed = stable_seed()
        request = build_production_request("plushbound_tileset_source", PROMPT, seed=seed)
        expected = {
            "model_id": MODEL_ID, "renderer_route": "flux2_klein", "width": 384, "height": 384,
            "steps": 4, "guidance_scale": 1.0, "bounded_production_authorized": True,
            "automatic_full_production_authorized": False, "catalog_wide_launch_authorized": False,
            "production_style_validated": True, "production_style_profile": "plushbound_tileset_source",
        }
        for key, value in expected.items():
            if request.get(key) != value:
                raise RuntimeError(f"{key} invariant changed: {request.get(key)!r} != {value!r}")

        generator = self.torch.Generator(device="cuda").manual_seed(seed)
        started = time.monotonic()
        result = self.pipe(
            prompt=PROMPT, width=384, height=384, guidance_scale=1.0, num_inference_steps=4, generator=generator
        ).images[0]
        elapsed = time.monotonic() - started
        raw_buf = io.BytesIO(); result.save(raw_buf, format="PNG"); raw = raw_buf.getvalue()
        payload = {"image_base64": base64.b64encode(raw).decode("ascii"), "width": 384, "height": 384, "seed": seed}
        inspection = inspect_generation({
            "asset_id": ASSET_ID, "material_key": "straw_thatch", "region": "elyndor",
            "target_sheet_type": "A5", "preset": "plushbound_tileset_source", "asset_class": "tileset_master",
        }, payload)
        with Image.open(io.BytesIO(raw)) as generated:
            normalized = normalize_image(generated)
        edge = edge_discontinuity(normalized)
        stddev = rgb_stddev(normalized)
        norm_buf = io.BytesIO(); normalized.save(norm_buf, format="PNG"); norm = norm_buf.getvalue()
        normalizer_accepted = edge <= MAX_EDGE_DISCONTINUITY and stddev >= MIN_RGB_STDDEV
        accepted = bool(inspection["accepted"]) and normalizer_accepted
        return {
            "schema": "plushbound.tileset_source_targeted_repair_report.v1",
            "version": VERSION,
            "asset_id": ASSET_ID,
            "generation_count": 1,
            "generation_retry_count": 0,
            "seed": seed,
            "elapsed_seconds": round(elapsed, 3),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "normalized_sha256": hashlib.sha256(norm).hexdigest(),
            "raw_inspection": inspection,
            "edge_discontinuity": round(edge, 6),
            "maximum_edge_discontinuity": MAX_EDGE_DISCONTINUITY,
            "rgb_stddev": round(stddev, 4),
            "minimum_rgb_stddev": MIN_RGB_STDDEV,
            "normalizer_accepted": normalizer_accepted,
            "accepted": accepted,
            "quarantined": not accepted,
            "full_A5_expansion_authorized": False,
            "catalog_wide_launch_authorized": False,
            "raw_png_base64": payload["image_base64"],
            "normalized_png_base64": base64.b64encode(norm).decode("ascii"),
        }


@app.local_entrypoint()
def main():
    report = StrawRepairRunner().run.remote()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(report.pop("raw_png_base64"))
    norm = base64.b64decode(report.pop("normalized_png_base64"))
    if hashlib.sha256(raw).hexdigest() != report["raw_sha256"] or hashlib.sha256(norm).hexdigest() != report["normalized_sha256"]:
        raise RuntimeError("targeted straw repair artifact hash mismatch")
    (OUTPUT_DIR / "straw_thatch-384.png").write_bytes(raw)
    (OUTPUT_DIR / "straw_thatch-48.png").write_bytes(norm)
    (OUTPUT_DIR / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in {"raw_inspection"}}, sort_keys=True))
    if report["generation_count"] != 1 or report["generation_retry_count"] != 0:
        raise RuntimeError("targeted straw repair violated one-generation hard cap")
    if not report["accepted"]:
        raise RuntimeError("targeted straw repair failed deterministic gate")
