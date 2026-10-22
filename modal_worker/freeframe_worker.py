"""FreeFrame headless Modal worker.

This is deliberately isolated from the Android app. It provides a serverless GPU
execution surface for FreeFrame-compatible image generation and asset batches.
Model weights are cached in a persistent Modal Volume and are never committed to
this repository.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import time
from dataclasses import dataclass

import modal

APP_NAME = "freeframe-worker"
MODEL_VOLUME = "freeframe-model-cache"
CACHE_DIR = "/cache"
DEFAULT_MODEL = os.environ.get("FREEFRAME_MODEL", "stabilityai/sd-turbo")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "accelerate>=1.1,<2",
        "diffusers>=0.31,<1",
        "fastapi>=0.115,<1",
        "huggingface-hub>=0.26,<1",
        "pillow>=10.4,<12",
        "safetensors>=0.4,<1",
        "torch>=2.4,<3",
        "transformers>=4.46,<5",
    )
)

app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


@dataclass(frozen=True)
class GenerationSpec:
    prompt: str
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    steps: int = 4
    guidance_scale: float = 0.0
    seed: int = 0

    def validate(self) -> None:
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if self.width < 64 or self.height < 64 or self.width > 1536 or self.height > 1536:
            raise ValueError("width/height must be between 64 and 1536")
        if self.width % 8 or self.height % 8:
            raise ValueError("width/height must be divisible by 8")
        if not 1 <= self.steps <= 100:
            raise ValueError("steps must be between 1 and 100")


def _png_payload(image) -> dict:
    out = io.BytesIO()
    image.save(out, format="PNG")
    raw = out.getvalue()
    return {
        "mime_type": "image/png",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "image_base64": base64.b64encode(raw).decode("ascii"),
        "width": image.width,
        "height": image.height,
    }


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    timeout=900,
)
class FreeFrameGenerator:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import AutoPipelineForText2Image

        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.model_name = DEFAULT_MODEL
        self.pipe = AutoPipelineForText2Image.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16,
            cache_dir=CACHE_DIR,
        ).to("cuda")

    @modal.method()
    def generate(self, request: dict) -> dict:
        started = time.monotonic()
        spec = GenerationSpec(
            prompt=str(request.get("prompt", "")),
            negative_prompt=str(request.get("negative_prompt", "")),
            width=int(request.get("width", 512)),
            height=int(request.get("height", 512)),
            steps=int(request.get("steps", 4)),
            guidance_scale=float(request.get("guidance_scale", 0.0)),
            seed=int(request.get("seed", 0)),
        )
        spec.validate()
        generator = self.torch.Generator(device="cuda").manual_seed(spec.seed)
        result = self.pipe(
            prompt=spec.prompt,
            negative_prompt=spec.negative_prompt or None,
            width=spec.width,
            height=spec.height,
            num_inference_steps=spec.steps,
            guidance_scale=spec.guidance_scale,
            generator=generator,
        ).images[0]
        payload = _png_payload(result)
        payload.update({
            "seed": spec.seed,
            "model": self.model_name,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        })
        return payload

    @modal.method()
    def generate_batch(self, requests: list[dict]) -> list[dict]:
        if not requests:
            return []
        if len(requests) > 32:
            raise ValueError("single worker batch is limited to 32 items")
        return [self.generate.local(req) for req in requests]


@app.function(image=image)
@modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
def health() -> dict:
    return {
        "service": APP_NAME,
        "status": "ok",
        "model": DEFAULT_MODEL,
        "gpu_profile": "L4",
    }


@app.function(image=image, timeout=30)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def validate_asset(request: dict) -> dict:
    """CPU-side integrity check used before/after expensive GPU work."""
    from PIL import Image

    encoded = request.get("image_base64")
    if not encoded:
        raise ValueError("image_base64 is required")
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("image exceeds 32 MiB validation limit")
    with Image.open(io.BytesIO(raw)) as img:
        img.verify()
    with Image.open(io.BytesIO(raw)) as img:
        return {
            "valid": True,
            "format": img.format,
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "has_alpha": "A" in img.getbands(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }


@app.function(image=image, timeout=930)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def generate_image(request: dict) -> dict:
    """Authenticated HTTP bridge to the GPU generator."""
    GenerationSpec(
        prompt=str(request.get("prompt", "")),
        negative_prompt=str(request.get("negative_prompt", "")),
        width=int(request.get("width", 512)),
        height=int(request.get("height", 512)),
        steps=int(request.get("steps", 4)),
        guidance_scale=float(request.get("guidance_scale", 0.0)),
        seed=int(request.get("seed", 0)),
    ).validate()
    return FreeFrameGenerator().generate.remote(request)
