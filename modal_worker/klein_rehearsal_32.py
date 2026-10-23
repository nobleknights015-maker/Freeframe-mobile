"""Bounded 32-asset FLUX.2 Klein production rehearsal with retry inspection.

Runs the current production request builder across eight deterministic requests per
major asset class. Obvious grid/model-sheet failures are inspected in-process and
retried with the same bounded deterministic seed policy used by production. This
script never authorizes the full 22k batch.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time

import modal

APP_NAME = "freeframe-klein-rehearsal-32"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUTPUT_DIR = "klein-rehearsal-32"

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


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=120, timeout=1200)
class KleinRehearsalRunner:
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
    def run_all(self) -> dict:
        from modal_worker.gpu_rehearsal_plan import rehearsal_requests
        from modal_worker.model_catalog import apply_model_defaults, get_candidate
        from modal_worker.production_inspector import inspect_generation
        from modal_worker.production_retry_policy import DEFAULT_PRODUCTION_RETRY_POLICY

        candidate = get_candidate("flux2_klein_4b_candidate")
        retry = DEFAULT_PRODUCTION_RETRY_POLICY
        outputs = []
        total_gpu_seconds = 0.0
        started = time.monotonic()

        for item in rehearsal_requests():
            base_request = apply_model_defaults(item["request"], candidate)
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
                    "preset": item["preset"],
                    "attempt": attempt,
                    "seed": int(request["seed"]),
                    "elapsed_seconds": round(elapsed, 3),
                    "inspection": inspection,
                    "png_base64": payload["image_base64"],
                }
                if inspection["accepted"]:
                    accepted = True
                    break
            final["accepted"] = accepted
            final["quarantined"] = not accepted
            outputs.append(final)

        accepted_count = sum(1 for x in outputs if x["accepted"])
        retry_count = sum(max(0, int(x["attempt"]) - 1) for x in outputs)
        return {
            "version": "klein-rehearsal-32-v1",
            "model": MODEL_ID,
            "gpu": "L4",
            "count": len(outputs),
            "accepted": accepted_count,
            "quarantined": len(outputs) - accepted_count,
            "retry_generations": retry_count,
            "completion_rate": accepted_count / len(outputs),
            "total_gpu_seconds": round(total_gpu_seconds, 3),
            "wall_seconds": round(time.monotonic() - started, 3),
            "full_production_authorized": False,
            "outputs": outputs,
        }


@app.local_entrypoint()
def main():
    import pathlib

    report = KleinRehearsalRunner().run_all.remote()
    out_dir = pathlib.Path(OUTPUT_DIR)
    out_dir.mkdir(exist_ok=True)
    manifest = []
    for item in report.pop("outputs"):
        encoded = item.pop("png_base64")
        path = out_dir / f"{item['asset_id']}.png"
        path.write_bytes(base64.b64decode(encoded))
        item["path"] = str(path)
        manifest.append(item)
    report["assets"] = manifest
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "assets"}, sort_keys=True))
