"""Bounded FINAL-production canary for Plushbound maps/world environment masters.

This is the first paid stage after the dedicated no-spend preflight. It is deliberately
limited to at most eight environment masters, uses only the promoted FreeFrame Klein
production route, retries/quarantines through the existing production inspector, and
never authorizes a catalog-wide launch.
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

APP_NAME = "freeframe-world-map-final-canary"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUTPUT_DIR = "world-map-final-canary"
CANARY_VERSION = "plushbound-world-map-final-canary-v1"
MAX_CANARY_ASSETS = 8

# Canonical Plushtopia region identities. The final two regions remain intentionally
# outside this first paid wave so the canary cannot exceed the approved 8-asset cap.
REGION_PROMPTS = (
    (
        "elyndor",
        "Sunny Plains of Elyndor, broad pastoral stitched grasslands and wildflowers, a clear winding starter road crossing an active Waystitch route, patchwork farm fields and a small handcrafted village in the distance, gentle hills around the landmark Bent Mile, bright welcoming daylight",
    ),
    (
        "crownweave",
        "Crownweave ceremonial highlands, an old civic road converging on historic Threadworks, formal terraced gardens, stately woven-stone institutional architecture and palace roofs in the distance, academies and guild districts layered across the highland city, polished but lived-in civic fantasy landscape",
    ),
    (
        "silkspire",
        "Silkspire vertical urban region, steep terraced streets and bridges climbing between elegant woven architecture, textile guild workshops, Threadcraft research towers and market courtyards, the Unfinished Spire rising as a distant landmark, clear traversable route through a dense vertical JRPG cityscape",
    ),
    (
        "gloamfen",
        "Gloamfen wetland, dim silver fog over shallow water, moss and fungi, luminous roots, weathered boardwalks connecting raised shelters, drowned ruins and the distant Sunk Loom, layered reeds and wetland vegetation with a clearly readable safe route through the marsh",
    ),
    (
        "verdancia",
        "Verdancia Grove-resonant wilderness, lush living infrastructure woven through immense trees, herb gardens and orchards, organic bridges and root paths, mossy clearings and the distant Hollow Canopy, vibrant healthy vegetation with a readable exploratory route through a living forest settlement",
    ),
    (
        "tideglass-coast",
        "Tideglass Coast, reflective shoreline and sea-glass cliffs crossed by luminous tidal Thread channels, a clear coastal path descending toward a maritime settlement and harbor, weathered woven docks and distant Mirrorwake Grotto, bright ocean air and layered traversable coastline",
    ),
    (
        "moonpatch-steppe",
        "Moonpatch Steppe at luminous night, wide silver-blue grassland under a large moon, long route-cloths and caravan tracks guiding travel across open terrain, scattered wayposts and a distant traveling camp, the Moonless Track visible as a darker landmark through the glowing grassland",
    ),
    (
        "sunspool-desert",
        "Sunspool Desert, sweeping warm dunes crossed by ancient spool-like travel routes, heat-resistant woven shelters around a distant oasis, partially buried Waystitch infrastructure and salvage ruins, the Buried Bobbin landmark emerging from the sand, clear traversable path despite heat haze",
    ),
    (
        "cinderreach",
        "Cinderreach volcanic geothermal region, stable Ember resonance glowing through dark rock seams, safe basalt roads between forge settlements, steam vents and industrial foundry structures, the Red Seam Foundry in the distance, intense but controlled heat with a clear traversable route",
    ),
    (
        "frostlace",
        "Frostlace northern ice region, lace-like frozen Thread formations across snowy valleys, preserved archive structures built into blue-white cliffs, warm sheltered route markers and the distant Crystal Hem, crisp cold atmosphere with a clear safe path through the frozen landscape",
    ),
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


def stable_seed(asset_id: str) -> int:
    digest = hashlib.sha256(f"{CANARY_VERSION}:{asset_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def canary_assets(limit: int = MAX_CANARY_ASSETS) -> list[dict]:
    limit = int(limit)
    if not 1 <= limit <= MAX_CANARY_ASSETS:
        raise ValueError(f"bounded world canary limit must be between 1 and {MAX_CANARY_ASSETS}")
    rows = []
    for region, prompt in REGION_PROMPTS[:limit]:
        asset_id = f"world.{region}.environment_master"
        rows.append(
            {
                "asset_id": asset_id,
                "region": region,
                "role": "environment_master",
                "preset": "plushbound_environment",
                "asset_class": "environment_master",
                "prompt": prompt,
                "seed": stable_seed(asset_id),
            }
        )
    if len({row["asset_id"] for row in rows}) != len(rows):
        raise RuntimeError("duplicate world canary asset ID")
    return rows


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    timeout=1200,
)
class WorldMapFinalRunner:
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
    def run_assets(self, assets: list[dict]) -> dict:
        from modal_worker.production_inspector import inspect_generation
        from modal_worker.production_request_builder import build_production_request
        from modal_worker.production_retry_policy import DEFAULT_PRODUCTION_RETRY_POLICY

        if not 1 <= len(assets) <= MAX_CANARY_ASSETS:
            raise RuntimeError(f"paid world canary attempted {len(assets)} assets; hard cap is {MAX_CANARY_ASSETS}")
        if len({str(item["asset_id"]) for item in assets}) != len(assets):
            raise RuntimeError("paid world canary contains duplicate asset IDs")

        retry = DEFAULT_PRODUCTION_RETRY_POLICY
        outputs = []
        total_gpu_seconds = 0.0
        started = time.monotonic()

        for item in assets:
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
                        f"{item['asset_id']}: production request invariant {key}={base_request.get(key)!r} expected={expected!r}"
                    )

            accepted = False
            final = None
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
                    "asset_id": item["asset_id"],
                    "region": item["region"],
                    "role": item["role"],
                    "preset": item["preset"],
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
                raise RuntimeError(f"{item['asset_id']}: no generation attempt was made")
            final["accepted"] = accepted
            final["quarantined"] = not accepted
            outputs.append(final)

        accepted_count = sum(1 for row in outputs if row["accepted"])
        retry_generations = sum(max(0, int(row["attempt"]) - 1) for row in outputs)
        return {
            "schema": "plushbound.world_map_final_canary_report.v1",
            "version": CANARY_VERSION,
            "model": MODEL_ID,
            "gpu": "L4",
            "requested_count": len(assets),
            "accepted_count": accepted_count,
            "quarantined_count": len(outputs) - accepted_count,
            "retry_generations": retry_generations,
            "total_gpu_seconds": round(total_gpu_seconds, 3),
            "wall_seconds": round(time.monotonic() - started, 3),
            "bounded_production_authorized": True,
            "catalog_wide_launch_authorized": False,
            "outputs": outputs,
        }


@app.local_entrypoint()
def main(limit: int = MAX_CANARY_ASSETS):
    assets = canary_assets(limit)
    report = WorldMapFinalRunner().run_assets.remote(assets)

    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(exist_ok=True)
    manifest = []
    for item in report.pop("outputs"):
        encoded = item.pop("png_base64")
        raw = base64.b64decode(encoded)
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise RuntimeError(f"{item['asset_id']}: local output hash mismatch")
        path = out_dir / f"{item['region']}-environment-master.png"
        path.write_bytes(raw)
        item["path"] = str(path)
        manifest.append(item)

    report["assets"] = manifest
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "assets"}, sort_keys=True))

    if report["requested_count"] > MAX_CANARY_ASSETS:
        raise RuntimeError("world canary exceeded hard asset cap")
    if report["quarantined_count"] != 0 or report["accepted_count"] != report["requested_count"]:
        raise RuntimeError("world canary did not pass deterministic production inspection; scaling is blocked")
