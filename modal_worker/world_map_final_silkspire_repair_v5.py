"""Single-asset FINAL-production repair for Silkspire environment master.

This producer exists only to replace the one remaining quarantined world-map canary asset.
It deliberately changes composition from a street-level scene to a distant establishing view
so the generator has no reason to invent storefront signs, banners, or heraldry.
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

APP_NAME = "freeframe-world-map-silkspire-v5"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
VERSION = "plushbound-world-map-final-repair-v5-silkspire-distant-structure"
ASSET_ID = "world.silkspire.environment_master"
REGION = "silkspire"
OUTPUT_DIR = "world-map-final-repair-v5"

PROMPT = (
    "Silkspire as a wide distant establishing landscape viewed from an opposite cliff, a vertical handcrafted fantasy city rising "
    "through a deep green ravine. Layered timber-and-pale-stone buildings, roof tiles, masonry terraces, stairs and narrow pedestrian "
    "bridges occupy the midground and background only; there are no close-up storefronts or facade details. A single slender unfinished "
    "fantasy tower of stone and timber rises in the far distance, clearly not a modern metal landmark. The composition emphasizes cliffs, "
    "architecture, depth and traversal routes rather than decoration. Every building surface is plain and structural. Scene contains zero "
    "fabric objects and zero hanging objects: no banners, no flags, no pennants, no awnings, no curtains, no drapes, no signs, no plaques, "
    "no posters, no shop boards, no market stalls, no emblems, no crests, no logos, no lettering, no numbers, no clock faces, no symbols, "
    "no glyphs, no runes, no heraldry and no ornamental markings. Quiet unoccupied JRPG fantasy cityscape, clean readable silhouette, "
    "original Plushbound handcrafted aesthetic, completely free of signage and symbolic decoration."
)

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


def stable_seed() -> int:
    digest = hashlib.sha256(f"{VERSION}:{ASSET_ID}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def asset() -> dict:
    return {
        "asset_id": ASSET_ID,
        "region": REGION,
        "role": "environment_master",
        "preset": "plushbound_environment",
        "asset_class": "environment_master",
        "prompt": PROMPT,
        "seed": stable_seed(),
    }


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    timeout=1200,
)
class SilkspireRepairV5Runner:
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
    def run(self, item: dict) -> dict:
        from modal_worker.production_inspector import inspect_generation
        from modal_worker.production_request_builder import build_production_request
        from modal_worker.production_retry_policy import DEFAULT_PRODUCTION_RETRY_POLICY

        if item["asset_id"] != ASSET_ID or item["region"] != REGION:
            raise RuntimeError("Silkspire V5 producer is hard-locked to exactly one asset ID")

        base_request = build_production_request(
            "plushbound_environment",
            str(item["prompt"]),
            seed=int(item["seed"]),
        )
        invariants = {
            "model_id": MODEL_ID,
            "renderer_route": "flux2_klein",
            "width": 1024,
            "height": 768,
            "steps": 4,
            "guidance_scale": 1.0,
            "bounded_production_authorized": True,
            "automatic_full_production_authorized": False,
            "catalog_wide_launch_authorized": False,
        }
        for key, expected in invariants.items():
            if base_request.get(key) != expected:
                raise RuntimeError(
                    f"{ASSET_ID}: production request invariant {key}={base_request.get(key)!r} expected={expected!r}"
                )

        retry = DEFAULT_PRODUCTION_RETRY_POLICY
        started = time.monotonic()
        total_gpu_seconds = 0.0
        final = None
        accepted = False
        for attempt in range(1, retry.max_attempts + 1):
            request = retry.variant(base_request, attempt)
            raw, elapsed = self._render(request)
            total_gpu_seconds += elapsed
            payload = {
                "image_base64": base64.b64encode(raw).decode("ascii"),
                "width": int(request["width"]),
                "height": int(request["height"]),
                "seed": int(request["seed"]),
            }
            inspection = inspect_generation(item, payload)
            final = {
                "asset_id": ASSET_ID,
                "region": REGION,
                "role": "environment_master",
                "preset": "plushbound_environment",
                "wave_mode": "repair-v5",
                "model_id": MODEL_ID,
                "renderer_route": "flux2_klein",
                "attempt": attempt,
                "seed": int(request["seed"]),
                "width": int(request["width"]),
                "height": int(request["height"]),
                "steps": int(request["steps"]),
                "guidance_scale": float(request["guidance_scale"]),
                "elapsed_seconds": round(elapsed, 3),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "inspection": inspection,
                "png_base64": payload["image_base64"],
            }
            if inspection["accepted"]:
                accepted = True
                break

        if final is None:
            raise RuntimeError("Silkspire V5 made no generation attempt")
        final["accepted"] = accepted
        final["quarantined"] = not accepted
        return {
            "schema": "plushbound.world_map_final_silkspire_repair_v5_report.v1",
            "version": VERSION,
            "wave_mode": "repair-v5",
            "model": MODEL_ID,
            "gpu": "L4",
            "requested_count": 1,
            "accepted_count": 1 if accepted else 0,
            "quarantined_count": 0 if accepted else 1,
            "retry_generations": max(0, int(final["attempt"]) - 1),
            "total_gpu_seconds": round(total_gpu_seconds, 3),
            "wall_seconds": round(time.monotonic() - started, 3),
            "bounded_production_authorized": True,
            "catalog_wide_launch_authorized": False,
            "output": final,
        }


@app.local_entrypoint()
def main():
    report = SilkspireRepairV5Runner().run.remote(asset())
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(exist_ok=True)
    item = report.pop("output")
    encoded = item.pop("png_base64")
    raw = base64.b64decode(encoded)
    if hashlib.sha256(raw).hexdigest() != item["sha256"]:
        raise RuntimeError("Silkspire V5 local output hash mismatch")
    path = out_dir / "silkspire-environment-master.png"
    path.write_bytes(raw)
    item["path"] = str(path)
    report["asset"] = item
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "asset"}, sort_keys=True))

    if report["quarantined_count"] != 0 or report["accepted_count"] != 1:
        raise RuntimeError("Silkspire Repair V5 failed deterministic production inspection")
