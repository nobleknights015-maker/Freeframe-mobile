"""FreeFrame Modal GPU worker."""
from __future__ import annotations

import base64
import hashlib
import io
import os
import time
from dataclasses import asdict, dataclass

import modal

APP_NAME = "freeframe-worker"
DEFAULT_MODEL = os.environ.get("FREEFRAME_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")
CACHE_DIR = "/model-cache"

app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name("freeframe-model-cache", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.11")
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
    .add_local_python_source("modal_worker")
)


@dataclass(frozen=True)
class GenerationSpec:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    guidance_scale: float
    seed: int

    @classmethod
    def from_request(cls, request: dict) -> "GenerationSpec":
        return cls(
            prompt=str(request.get("prompt", "")).strip(),
            negative_prompt=str(request.get("negative_prompt", "")).strip(),
            width=int(request.get("width", 768)),
            height=int(request.get("height", 768)),
            steps=int(request.get("steps", 28)),
            guidance_scale=float(request.get("guidance_scale", 6.0)),
            seed=int(request.get("seed", 0)),
        )

    def validate(self) -> None:
        if not self.prompt:
            raise ValueError("prompt is required")
        if self.width < 256 or self.height < 256 or self.width > 1536 or self.height > 1536:
            raise ValueError("width and height must be between 256 and 1536")
        if self.width % 8 or self.height % 8:
            raise ValueError("width and height must be divisible by 8")
        if self.steps < 1 or self.steps > 100:
            raise ValueError("steps must be between 1 and 100")
        if self.guidance_scale < 0 or self.guidance_scale > 30:
            raise ValueError("guidance_scale must be between 0 and 30")
        if self.seed < 0 or self.seed > 2**32 - 1:
            raise ValueError("seed must be a uint32")


def _png_payload(image_obj) -> dict:
    out = io.BytesIO()
    image_obj.save(out, format="PNG", optimize=False)
    raw = out.getvalue()
    return {
        "mime_type": "image/png",
        "image_base64": base64.b64encode(raw).decode("ascii"),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "width": image_obj.width,
        "height": image_obj.height,
    }


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=120, timeout=900)
class FreeFrameGenerator:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import AutoPipelineForText2Image

        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.model_name = DEFAULT_MODEL
        load_kwargs = {"torch_dtype": torch.float16, "cache_dir": CACHE_DIR}
        if self.model_name == "stabilityai/stable-diffusion-xl-base-1.0":
            load_kwargs.update({"variant": "fp16", "use_safetensors": True})
        self.pipe = AutoPipelineForText2Image.from_pretrained(self.model_name, **load_kwargs).to("cuda")

    def _generate_one(self, request: dict) -> dict:
        started = time.monotonic()
        spec = GenerationSpec.from_request(request)
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
        payload.update({"seed": spec.seed, "model": self.model_name, "elapsed_seconds": round(time.monotonic() - started, 3), "generation_spec": asdict(spec)})
        return payload

    @modal.method()
    def generate(self, request: dict) -> dict:
        return self._generate_one(request)

    @modal.method()
    def generate_batch(self, requests: list[dict]) -> list[dict]:
        if not requests:
            return []
        if len(requests) > 32:
            raise ValueError("single worker batch is limited to 32 items")
        return [self._generate_one(req) for req in requests]


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=120, timeout=900)
class FreeFrameExtractor:
    """Dedicated cached GPU subject extractor; isolated from SDXL VRAM state."""

    @modal.enter()
    def load(self):
        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        from modal_worker.birefnet_extractor import BiRefNetExtractor
        self.extractor = BiRefNetExtractor()

    @modal.method()
    def extract(self, request: dict) -> dict:
        from modal_worker.extraction_provider import extract_and_validate

        encoded = request.get("image_base64")
        if not encoded:
            raise ValueError("image_base64 is required")
        source = base64.b64decode(encoded, validate=True)
        if len(source) > 32 * 1024 * 1024:
            raise ValueError("image exceeds 32 MiB extraction limit")
        started = time.monotonic()
        output_png, metadata = extract_and_validate(source, self.extractor)
        return {
            "mime_type": "image/png",
            "image_base64": base64.b64encode(output_png).decode("ascii"),
            "bytes": len(output_png),
            "sha256": metadata["output_sha256"],
            "width": metadata["output_width"],
            "height": metadata["output_height"],
            "provider": metadata["extraction_provider"],
            "model": metadata["extraction_model"],
            "metadata": metadata,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }


@app.function(image=image)
@modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
def health() -> dict:
    return {"service": APP_NAME, "status": "ok", "model": DEFAULT_MODEL, "gpu_profile": "L4"}


@app.function(image=image, timeout=30)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def validate_asset(request: dict) -> dict:
    from PIL import Image
    from modal_worker.asset_profiles import validate_metadata

    encoded = request.get("image_base64")
    if not encoded:
        raise ValueError("image_base64 is required")
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("image exceeds 32 MiB validation limit")
    with Image.open(io.BytesIO(raw)) as img:
        img.verify()
    with Image.open(io.BytesIO(raw)) as img:
        metadata = {"format": img.format, "width": img.width, "height": img.height, "mode": img.mode, "has_alpha": "A" in img.getbands(), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}

    profile_name = request.get("profile")
    profile_result = None
    if profile_name:
        profile_result = validate_metadata(profile_name=str(profile_name), fmt=str(metadata["format"] or ""), width=int(metadata["width"]), height=int(metadata["height"]), has_alpha=bool(metadata["has_alpha"]))
    return {"valid": profile_result["valid"] if profile_result else True, **metadata, "profile_validation": profile_result}


@app.function(image=image, timeout=930)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def generate_image(request: dict) -> dict:
    spec = GenerationSpec.from_request(request)
    spec.validate()
    return FreeFrameGenerator().generate.remote(request)


@app.function(image=image, timeout=930)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def extract_subject(request: dict) -> dict:
    """Authenticated HTTP bridge to the dedicated GPU extraction worker."""
    return FreeFrameExtractor().extract.remote(request)
