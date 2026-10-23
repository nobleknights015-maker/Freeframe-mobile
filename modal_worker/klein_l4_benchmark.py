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
QUALITY_CALIBRATION_STEPS = 4
QUALITY_CALIBRATION_GUIDANCE = 1.0
REFERENCE_CASE_ID = "penney_modeling_stress"
GUARDIAN_CASE_ID = "guardian_meadow"
MIN_REFERENCE_EDGE = 64

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


def select_case(case_id: str) -> dict:
    from modal_worker.benchmark_plan import CASES
    from modal_worker.model_catalog import apply_model_defaults, get_candidate
    from modal_worker.production_style_policy import apply_production_style
    from modal_worker.style_profiles import get_style_profile

    matches = [case for case in CASES if case.case_id == case_id]
    if len(matches) != 1:
        raise ValueError(f"unknown benchmark case: {case_id}")
    case = matches[0]
    request = case.request()
    request = apply_production_style(case.preset, request)

    # Guardian remains intentionally unpromoted in production. Apply its candidate
    # profile only inside this bounded calibration so visual QA can earn promotion.
    if case_id == GUARDIAN_CASE_ID:
        request = get_style_profile("plushbound_guardian_2d_candidate").apply(request)
        request["benchmark_candidate_style"] = "plushbound_guardian_2d_candidate"

    candidate = get_candidate("flux2_klein_4b_candidate")
    request = apply_model_defaults(request, candidate)
    request["steps"] = QUALITY_CALIBRATION_STEPS
    request["guidance_scale"] = QUALITY_CALIBRATION_GUIDANCE
    if case_id == REFERENCE_CASE_ID:
        request["quality_calibration"] = "ordered-dual-user-reference"
    elif case_id == GUARDIAN_CASE_ID:
        request["quality_calibration"] = "guardian-candidate-style"
    else:
        request["quality_calibration"] = "official-distilled-defaults"
    request["reference_conditioned"] = case_id == REFERENCE_CASE_ID
    if case_id == REFERENCE_CASE_ID:
        request["prompt"] = (
            "Use reference image 1 only for contemporary rendering quality, realistic material response, dimensional skin lighting, "
            "body proportion and polished high-end digital finish while keeping the final image a stylized 2D JRPG illustration, not photorealistic. "
            "Use reference image 2 for Penney's Plushbound identity, pink hair, flower ornaments, face language and character canon. "
            + str(request["prompt"])
        )
    if request["width"] % 16 or request["height"] % 16:
        raise ValueError("Klein benchmark dimensions must be divisible by 16")
    return request


def _decode_reference(encoded: str):
    from PIL import Image

    raw = base64.b64decode(encoded)
    reference = Image.open(io.BytesIO(raw)).convert("RGB")
    width, height = reference.size
    shortest = min(width, height)
    if shortest < MIN_REFERENCE_EDGE:
        scale = MIN_REFERENCE_EDGE / shortest
        target = (
            max(MIN_REFERENCE_EDGE, round(width * scale)),
            max(MIN_REFERENCE_EDGE, round(height * scale)),
        )
        reference = reference.resize(target, Image.Resampling.LANCZOS)
    return reference


def load_calibration_references():
    from modal_worker.calibration_reference_assets import PENNEY_CANON_REFERENCE_JPEG_BASE64
    from modal_worker.calibration_reference_modern import PENNEY_MODERN_FULLBODY_JPEG_BASE64

    return [
        _decode_reference(PENNEY_MODERN_FULLBODY_JPEG_BASE64),
        _decode_reference(PENNEY_CANON_REFERENCE_JPEG_BASE64),
    ]


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
        kwargs = {
            "prompt": str(request["prompt"]),
            "width": int(request["width"]),
            "height": int(request["height"]),
            "guidance_scale": float(request["guidance_scale"]),
            "num_inference_steps": int(request["steps"]),
            "generator": generator,
        }
        if request["reference_conditioned"]:
            kwargs["image"] = load_calibration_references()

        started = time.monotonic()
        result = self.pipe(**kwargs).images[0]
        elapsed = round(time.monotonic() - started, 3)
        out = io.BytesIO()
        result.save(out, format="PNG")
        raw = out.getvalue()
        return {
            "benchmark_version": "klein-l4-v13-guardian-candidate-calibration",
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
            "quality_calibration": request.get("quality_calibration"),
            "reference_conditioned": bool(request.get("reference_conditioned")),
            "reference_count": 2 if request.get("reference_conditioned") else 0,
            "reference_source": (
                "user-owned modern full-body Penney crop first + project-owned Plushbound Penney portrait second"
                if request.get("reference_conditioned")
                else None
            ),
            "style_profile": request.get("render_style_profile"),
            "style_version": request.get("render_style_version"),
            "style_policy_version": request.get("production_style_policy_version"),
            "benchmark_candidate_style": request.get("benchmark_candidate_style"),
            "budget": benchmark_decision(elapsed),
            "production_authorized": False,
            "png_base64": base64.b64encode(raw).decode("ascii"),
        }


@app.local_entrypoint()
def main(case_id: str = "guardian_meadow"):
    result = KleinBenchmarkRunner().run_case.remote(case_id)
    png_base64 = result.pop("png_base64")
    with open(OUTPUT_PNG, "wb") as handle:
        handle.write(base64.b64decode(png_base64))
    result["output_png"] = OUTPUT_PNG
    print(json.dumps(result, sort_keys=True))
