"""Exact two-asset completion wave for the canonical Plushtopia environment-master baseline.

This producer is intentionally hard-locked to Cinderreach and Frostlace. The eight
accepted canary/repair assets are protected from regeneration. Catalog-wide production
remains unauthorized and 48px tilesets/playable map geometry remain separate lanes.
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

APP_NAME = "freeframe-world-map-baseline-completion"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
VERSION = "plushbound-world-map-baseline-completion-v1"
OUTPUT_DIR = "world-map-baseline-completion"
EXPECTED_REGIONS = ("cinderreach", "frostlace")

PROMPTS = {
    "cinderreach": (
        "Cinderreach, an original handcrafted JRPG volcanic geothermal region of dark basalt terraces, warm Ember resonance glowing "
        "naturally through narrow rock seams, controlled steam vents, compact forge-settlement buildings made from stone, timber and "
        "plain heat-resistant woven materials, and the Red Seam Foundry as a distant low industrial-fantasy landmark. Traversal uses "
        "rough irregular basalt stepping paths and compacted dark-earth wagon tracks integrated into the terrain, never a modern road. "
        "No asphalt, no smooth blacktop, no lane markings, no curbs, no guardrails, no road paint, no vehicles and no modern highway "
        "engineering. Keep all visible surfaces plain: no banners, flags, pennants, signs, plaques, posters, emblems, crests, logos, "
        "letters, numbers, glyphs, runes, pseudo-text, heraldry or symbolic markings. Intense but controlled heat, readable safe route, "
        "clean anime/JRPG environment composition, original Plushbound fabric-and-thread material language without readable decoration."
    ),
    "frostlace": (
        "Frostlace, an original handcrafted JRPG northern ice region of broad snowy valleys, blue-white cliffs and lace-like frozen Thread "
        "formations occurring naturally in ice, with plain archive structures carved into distant cliffs and the Crystal Hem as a natural "
        "far-off frozen landmark. Traversal is a narrow packed-snow footpath with irregular wind-softened edges and occasional exposed "
        "stone, clearly safe but entirely natural. No paved roadway, no glossy ice highway, no lane markings, no curbs, no guardrails, no "
        "road signs and no modern infrastructure. Do not render route markers, signposts, banners, flags, pennants, plaques, emblems, "
        "crests, logos, letters, numbers, glyphs, runes, pseudo-text, heraldry or symbolic markings. Crisp cold atmosphere, readable "
        "fantasy traversal, clean anime/JRPG environment composition, original Plushbound fabric-and-thread material language with plain "
        "unmarked architecture and zero readable decoration."
    ),
}

PROTECTED_ACCEPTED_IDS = frozenset({
    "world.gloamfen.environment_master",
    "world.sunspool-desert.environment_master",
    "world.crownweave.environment_master",
    "world.tideglass-coast.environment_master",
    "world.verdancia.environment_master",
    "world.elyndor.environment_master",
    "world.moonpatch-steppe.environment_master",
    "world.silkspire.environment_master",
})

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


def assets() -> list[dict]:
    rows = []
    for region in EXPECTED_REGIONS:
        asset_id = f"world.{region}.environment_master"
        rows.append({
            "asset_id": asset_id,
            "region": region,
            "role": "environment_master",
            "preset": "plushbound_environment",
            "asset_class": "environment_master",
            "prompt": PROMPTS[region],
            "seed": stable_seed(asset_id),
        })
    ids = {row["asset_id"] for row in rows}
    if len(rows) != 2 or len(ids) != 2:
        raise RuntimeError("baseline completion must contain exactly two unique assets")
    if ids & PROTECTED_ACCEPTED_IDS:
        raise RuntimeError("baseline completion attempted to regenerate an accepted protected asset")
    if ids != {"world.cinderreach.environment_master", "world.frostlace.environment_master"}:
        raise RuntimeError("baseline completion asset set changed from exact canonical remainder")
    return rows


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    timeout=1200,
)
class BaselineCompletionRunner:
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
        from modal_worker.production_retry_policy import DEFAULT_PRODUCTION_RETRY_POLICY

        ids = {str(row["asset_id"]) for row in rows}
        expected = {"world.cinderreach.environment_master", "world.frostlace.environment_master"}
        if len(rows) != 2 or ids != expected or ids & PROTECTED_ACCEPTED_IDS:
            raise RuntimeError("remote baseline wave is not the exact protected two-asset remainder")

        retry = DEFAULT_PRODUCTION_RETRY_POLICY
        outputs = []
        total_gpu_seconds = 0.0
        started = time.monotonic()

        for item in rows:
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
            for key, expected_value in invariants.items():
                if base_request.get(key) != expected_value:
                    raise RuntimeError(
                        f"{item['asset_id']}: request invariant {key}={base_request.get(key)!r} expected={expected_value!r}"
                    )

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
                    "asset_id": item["asset_id"],
                    "region": item["region"],
                    "role": item["role"],
                    "preset": item["preset"],
                    "wave_mode": "baseline-completion",
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
        return {
            "schema": "plushbound.world_map_baseline_completion_report.v1",
            "version": VERSION,
            "wave_mode": "baseline-completion",
            "model": MODEL_ID,
            "gpu": "L4",
            "requested_count": 2,
            "accepted_count": accepted_count,
            "quarantined_count": 2 - accepted_count,
            "retry_generations": sum(max(0, int(row["attempt"]) - 1) for row in outputs),
            "total_gpu_seconds": round(total_gpu_seconds, 3),
            "wall_seconds": round(time.monotonic() - started, 3),
            "bounded_production_authorized": True,
            "catalog_wide_launch_authorized": False,
            "outputs": outputs,
        }


@app.local_entrypoint()
def main():
    report = BaselineCompletionRunner().run_assets.remote(assets())
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(exist_ok=True)
    manifest = []
    for item in report.pop("outputs"):
        raw = base64.b64decode(item.pop("png_base64"))
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise RuntimeError(f"{item['asset_id']}: local output hash mismatch")
        path = out_dir / f"{item['region']}-environment-master.png"
        path.write_bytes(raw)
        item["path"] = str(path)
        manifest.append(item)
    report["assets"] = manifest
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "assets"}, sort_keys=True))
    if report["accepted_count"] != 2 or report["quarantined_count"] != 0:
        raise RuntimeError("two-region baseline completion failed deterministic inspection")
