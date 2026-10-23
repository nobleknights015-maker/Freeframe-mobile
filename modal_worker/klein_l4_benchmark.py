"""Isolated FLUX.2 Klein 4B L4 benchmark for FreeFrame.

This app is intentionally separate from the production worker. It can measure one
representative Plushbound case at a time, project raw 22k GPU cost through the
budget gate, preserve the generated PNG for visual QA, and never authorize production.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time

import modal

APP_NAME = "freeframe-klein-benchmark"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUTPUT_PNG = "klein-l4-output.png"

# Follow the model card's supported install path: current Diffusers,
# Transformers, and Accelerate resolve together. Avoid cross-generation pins
# between huggingface-hub and Transformers that can make the image impossible
# to solve before GPU inference even begins.
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


# Mirrors the current production style policy for renderer calibration.
# Guardians remain unstyled until the dedicated 2D creature treatment is proven.
BENCHMARK_STYLE_POLICY = {
    "plushbound_character": "plushbound_trinity",
    "plushbound_enemy": "plushbound_trinity",
    "plushbound_environment": "plushbound_trinity",
}


def select_case(case_id: str) -> dict:
    from modal_worker.benchmark_plan import CASES
    from modal_worker.model_catalog import apply_model_defaults, get_candidate
    from modal_worker.style_profiles import get_style_profile

    matches = [case for case in CASES if case.case_id == case_id]
    if len(matches) != 1:
        raise ValueError(f"unknown benchmark case: {case_id}")
    case = matches[0]
    request = case.request()
    style_name = BENCHMARK_STYLE_POLICY.get(case.preset)
    if style_name:
        request = get_style_profile(style_name).apply(request)
    candidate = get_candidate("flux2_klein_4b_candidate")
    request = apply_model_defaults(request, candidate)
    if request["width"] % 16 or request["height"] % 16:
        raise ValueError("Klein benchmark dimensions must be divisible by 16")
    return request


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=60,
    timeout=1200,
)
class KleinBenchmarkRunner:
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

    @modal.method()
    def run_case(self, case_id: str) -> dict:
        from modal_worker.model_upgrade_budget import benchmark_decision

        request = select_case(case_id)
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
        elapsed = round(time.monotonic() - started, 3)
        out = io.BytesIO()
        result.save(out, format="PNG")
        raw = out.getvalue()
        return {
            "benchmark_version": "klein-l4-v3-style-calibration",
            "case_id": case_id,
            "model": MODEL_ID,
            "gpu": "L4",
            "elapsed_seconds": elapsed,
            "width": result.width,
            "height": result.height,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "steps": int(request["steps"]),
            "guidance_scale": float(request["guidance_scale"]),
            "seed": int(request["seed"]),
            "style_profile": request.get("render_style_profile"),
            "style_version": request.get("render_style_version"),
            "budget": benchmark_decision(elapsed),
            "production_authorized": False,
            "png_base64": base64.b64encode(raw).decode("ascii"),
        }


@app.local_entrypoint()
def main(case_id: str = "penney_modeling_stress"):
    result = KleinBenchmarkRunner().run_case.remote(case_id)
    png_base64 = result.pop("png_base64")
    with open(OUTPUT_PNG, "wb") as handle:
        handle.write(base64.b64decode(png_base64))
    result["output_png"] = OUTPUT_PNG
    print(json.dumps(result, sort_keys=True))
