"""Dedicated Vera FLUX.2 Klein reference-conditioned production worker.

This worker is intentionally isolated from the legacy FreeFrame production class.
It exists to prove the corrected Plushbound reference -> Vera/Modal -> generated
source-art path before any regional batch is reopened.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import time
from dataclasses import asdict, dataclass

import modal

APP_NAME = "freeframe-flux2-reference-worker"
MODEL_VOLUME = "freeframe-model-cache"
REFERENCE_VOLUME = "freeframe-reference-cache"
CACHE_DIR = "/cache"
REFERENCE_DIR = "/references"
PRODUCTION_MODEL = "black-forest-labs/FLUX.2-klein-4B"
PRODUCTION_RENDERER_ROUTE = "flux2_klein_reference_v2"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "accelerate>=1.1,<2",
        "diffusers>=0.37.1,<0.38",
        "huggingface-hub>=0.26,<1",
        "numpy>=1.26,<2",
        "pillow>=10.4,<12",
        "safetensors>=0.4,<1",
        "sentencepiece>=0.2,<1",
        "torch>=2.4,<3",
        "torchvision>=0.19,<1",
        "transformers>=4.51,<5",
    )
    .add_local_python_source("modal_worker")
)

app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)
reference_cache = modal.Volume.from_name(REFERENCE_VOLUME, create_if_missing=True)


@dataclass(frozen=True)
class GenerationSpec:
    prompt: str
    width: int = 384
    height: int = 384
    steps: int = 4
    guidance_scale: float = 1.0
    seed: int = 0

    @classmethod
    def from_request(cls, request: dict) -> "GenerationSpec":
        return cls(
            prompt=str(request.get("prompt", "")),
            width=int(request.get("width", 384)),
            height=int(request.get("height", 384)),
            steps=int(request.get("steps", 4)),
            guidance_scale=float(request.get("guidance_scale", 1.0)),
            seed=int(request.get("seed", 0)),
        )

    def validate(self) -> None:
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if self.width != 384 or self.height != 384:
            raise ValueError("reference canary is locked to 384x384")
        if self.width % 16 or self.height % 16:
            raise ValueError("FLUX.2 Klein dimensions must be divisible by 16")
        if self.steps != 4:
            raise ValueError("reference canary is locked to 4 steps")
        if self.guidance_scale != 1.0:
            raise ValueError("reference canary is locked to guidance_scale=1.0")
        if not 0 <= self.seed <= 2**63 - 1:
            raise ValueError("seed must be between 0 and 2^63-1")


def _png_payload(rendered_image) -> dict:
    out = io.BytesIO()
    rendered_image.save(out, format="PNG")
    raw = out.getvalue()
    return {
        "mime_type": "image/png",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "image_base64": base64.b64encode(raw).decode("ascii"),
        "width": rendered_image.width,
        "height": rendered_image.height,
    }


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache, REFERENCE_DIR: reference_cache},
    scaledown_window=120,
    timeout=1800,
)
class VeraFlux2ReferenceGenerator:
    """Official Flux2KleinPipeline path with CPU offload and reference input."""

    @modal.enter()
    def load(self):
        import diffusers
        import torch
        from diffusers import Flux2KleinPipeline

        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.model_name = PRODUCTION_MODEL
        print(
            f"VERA_FLUX2_LOAD=BEGIN model={PRODUCTION_MODEL} diffusers={diffusers.__version__}",
            flush=True,
        )
        started = time.monotonic()
        self.pipe = Flux2KleinPipeline.from_pretrained(
            PRODUCTION_MODEL,
            torch_dtype=torch.bfloat16,
            cache_dir=CACHE_DIR,
        )
        print(
            f"VERA_FLUX2_LOAD=MODEL_READY seconds={time.monotonic()-started:.3f}",
            flush=True,
        )
        self.pipe.enable_model_cpu_offload()
        self.pipe.set_progress_bar_config(disable=True)
        print("VERA_FLUX2_LOAD=CPU_OFFLOAD_READY", flush=True)

    def _load_reference(self, reference_id: str):
        from PIL import Image
        from modal_worker.reference_store import load_reference_bytes

        reference_cache.reload()
        raw = load_reference_bytes(reference_id, REFERENCE_DIR)
        if hashlib.sha256(raw).hexdigest() != reference_id:
            raise RuntimeError("stored reference hash mismatch")
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        return image, raw

    @modal.method()
    def generate(self, request: dict) -> dict:
        spec = GenerationSpec.from_request(request)
        spec.validate()
        if str(request.get("model_id", "")).strip() != PRODUCTION_MODEL:
            raise ValueError("model_id does not match dedicated Vera worker")
        if str(request.get("renderer_route", "")).strip() != PRODUCTION_RENDERER_ROUTE:
            raise ValueError("renderer_route does not match dedicated Vera worker")

        reference_id = str(request.get("reference_id", "")).strip().lower()
        if not reference_id or len(reference_id) != 64:
            raise ValueError("reference_id SHA-256 is required")
        if request.get("reference_sheet_pixels_used_as_runtime_art") is not False:
            raise ValueError("reference-sheet pixels must remain runtime-forbidden")

        print(f"VERA_FLUX2_GENERATE=REFERENCE_LOAD_BEGIN id={reference_id}", flush=True)
        reference, reference_raw = self._load_reference(reference_id)
        print(
            f"VERA_FLUX2_GENERATE=REFERENCE_READY size={reference.width}x{reference.height}",
            flush=True,
        )

        generator = self.torch.Generator(device="cuda").manual_seed(spec.seed)
        started = time.monotonic()
        print(
            f"VERA_FLUX2_GENERATE=PIPELINE_BEGIN seed={spec.seed} size={spec.width}x{spec.height}",
            flush=True,
        )
        rendered = self.pipe(
            prompt=spec.prompt,
            image=reference,
            width=spec.width,
            height=spec.height,
            num_inference_steps=spec.steps,
            guidance_scale=spec.guidance_scale,
            generator=generator,
        ).images[0]
        elapsed = time.monotonic() - started
        print(f"VERA_FLUX2_GENERATE=PIPELINE_DONE seconds={elapsed:.3f}", flush=True)

        payload = _png_payload(rendered)
        payload.update(
            {
                "seed": spec.seed,
                "model": self.model_name,
                "renderer_route": PRODUCTION_RENDERER_ROUTE,
                "elapsed_seconds": round(elapsed, 3),
                "generation_spec": asdict(spec),
                "source_art_provenance": "vera-modal-generated",
                "reference_sheet_pixels_used_as_runtime_art": False,
                "reference_conditioning": {
                    "reference_id": reference_id,
                    "reference_sha256": hashlib.sha256(reference_raw).hexdigest(),
                    "reference_mode": "style",
                    "reference_role": "regional_visual_material_authority_only",
                },
                "bounded_production": True,
                "automatic_full_production_authorized": False,
            }
        )
        return payload


@app.function(image=image, volumes={CACHE_DIR: model_cache}, timeout=60)
def inspect_model_cache() -> dict:
    """CPU-only cache inspection; does not instantiate a GPU renderer."""
    from pathlib import Path

    root = Path(CACHE_DIR)
    target = root / "models--black-forest-labs--FLUX.2-klein-4B"
    files = []
    total = 0
    if target.exists():
        for path in target.rglob("*"):
            if path.is_file():
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                total += size
                files.append(str(path.relative_to(target)))
    return {
        "model": PRODUCTION_MODEL,
        "cache_root_exists": root.exists(),
        "model_cache_exists": target.exists(),
        "file_count": len(files),
        "bytes": total,
        "sample_files": sorted(files)[:20],
    }
