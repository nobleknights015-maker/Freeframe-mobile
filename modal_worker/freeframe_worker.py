"""FreeFrame headless Modal worker.

This is deliberately isolated from the Android app. It provides a serverless GPU
execution surface for FreeFrame-compatible image generation, extraction, reference
storage, and deterministic Plushbound planning.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import time
from dataclasses import asdict, dataclass

import modal

APP_NAME = "freeframe-worker"
MODEL_VOLUME = "freeframe-model-cache"
REFERENCE_VOLUME = "freeframe-reference-cache"
CACHE_DIR = "/cache"
REFERENCE_DIR = "/references"
LEGACY_MODEL = os.environ.get("FREEFRAME_LEGACY_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")
PRODUCTION_MODEL = "black-forest-labs/FLUX.2-klein-4B"
PRODUCTION_RENDERER_ROUTE = "flux2_klein"
IP_ADAPTER_MODEL = "h94/IP-Adapter"
IP_ADAPTER_SUBFOLDER = "sdxl_models"
IP_ADAPTER_WEIGHT = "ip-adapter_sdxl.bin"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "accelerate>=1.1,<2", "diffusers>=0.31,<1", "einops>=0.8,<1", "fastapi>=0.115,<1", "huggingface-hub>=0.26,<1",
        "kornia>=0.7,<1", "numpy>=1.26,<2", "pillow>=10.4,<12", "safetensors>=0.4,<1", "sentencepiece>=0.2,<1", "timm>=1.0.23,<2",
        "torch>=2.4,<3", "torchvision>=0.19,<1", "transformers>=4.46,<5",
    )
    .add_local_python_source("modal_worker")
)

app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)
reference_cache = modal.Volume.from_name(REFERENCE_VOLUME, create_if_missing=True)


@dataclass(frozen=True)
class GenerationSpec:
    prompt: str
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    steps: int = 4
    guidance_scale: float = 0.0
    seed: int = 0

    @classmethod
    def from_request(cls, request: dict) -> "GenerationSpec":
        return cls(prompt=str(request.get("prompt", "")), negative_prompt=str(request.get("negative_prompt", "")), width=int(request.get("width", 512)), height=int(request.get("height", 512)), steps=int(request.get("steps", 4)), guidance_scale=float(request.get("guidance_scale", 0.0)), seed=int(request.get("seed", 0)))

    def validate(self) -> None:
        if not self.prompt.strip(): raise ValueError("prompt must not be empty")
        if self.width < 64 or self.height < 64 or self.width > 1536 or self.height > 1536: raise ValueError("width/height must be between 64 and 1536")
        if self.width % 8 or self.height % 8: raise ValueError("width/height must be divisible by 8")
        if not 1 <= self.steps <= 100: raise ValueError("steps must be between 1 and 100")
        if not 0 <= self.guidance_scale <= 30: raise ValueError("guidance_scale must be between 0 and 30")
        if not 0 <= self.seed <= 2**63 - 1: raise ValueError("seed must be between 0 and 2^63-1")


def _png_payload(rendered_image) -> dict:
    out = io.BytesIO(); rendered_image.save(out, format="PNG"); raw = out.getvalue()
    return {"mime_type":"image/png","sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"image_base64":base64.b64encode(raw).decode("ascii"),"width":rendered_image.width,"height":rendered_image.height}


def _reference_strength_text(scale: float) -> str:
    if scale < 0.25: return "lightly"
    if scale < 0.60: return "moderately"
    return "strongly"


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR:model_cache, REFERENCE_DIR:reference_cache}, scaledown_window=120, timeout=900)
class FreeFrameGenerator:
    """Legacy SDXL path retained for compatibility and isolated experiments."""
    @modal.enter()
    def load(self):
        import torch
        from diffusers import AutoPipelineForText2Image
        os.environ.setdefault("HF_HOME", CACHE_DIR); os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch=torch; self.model_name=LEGACY_MODEL; self.ip_adapter_loaded=False
        load_kwargs={"torch_dtype":torch.float16,"cache_dir":CACHE_DIR}
        if self.model_name=="stabilityai/stable-diffusion-xl-base-1.0": load_kwargs.update({"variant":"fp16","use_safetensors":True})
        self.pipe=AutoPipelineForText2Image.from_pretrained(self.model_name, **load_kwargs).to("cuda")

    def _ensure_ip_adapter(self):
        if self.ip_adapter_loaded: return
        if self.model_name!="stabilityai/stable-diffusion-xl-base-1.0": raise ValueError("reference-image conditioning is currently validated only for SDXL base 1.0")
        self.pipe.load_ip_adapter(IP_ADAPTER_MODEL, subfolder=IP_ADAPTER_SUBFOLDER, weight_name=IP_ADAPTER_WEIGHT, cache_dir=CACHE_DIR); self.ip_adapter_loaded=True

    def _load_cached_reference(self, reference_id:str)->bytes:
        from modal_worker.reference_store import load_reference_bytes
        reference_cache.reload(); return load_reference_bytes(reference_id, REFERENCE_DIR)

    def _generate_one(self, request:dict)->dict:
        from modal_worker.reference_conditioning import adapter_scale_for, parse_reference_conditioning
        started=time.monotonic(); spec=GenerationSpec.from_request(request); spec.validate(); reference=parse_reference_conditioning(request,resolver=self._load_cached_reference)
        generator=self.torch.Generator(device="cuda").manual_seed(spec.seed)
        kwargs={"prompt":spec.prompt,"negative_prompt":spec.negative_prompt or None,"width":spec.width,"height":spec.height,"num_inference_steps":spec.steps,"guidance_scale":spec.guidance_scale,"generator":generator}
        if reference is not None:
            self._ensure_ip_adapter(); self.pipe.set_ip_adapter_scale(adapter_scale_for(reference)); kwargs["ip_adapter_image"]=reference.image
        elif self.ip_adapter_loaded: self.pipe.set_ip_adapter_scale(0.0)
        result=self.pipe(**kwargs).images[0]; payload=_png_payload(result)
        payload.update({"seed":spec.seed,"model":self.model_name,"renderer_route":"legacy_sdxl","elapsed_seconds":round(time.monotonic()-started,3),"generation_spec":asdict(spec),"reference_conditioning":reference.metadata() if reference is not None else None,"negative_prompt_applied":True}); return payload

    @modal.method()
    def generate(self, request:dict)->dict: return self._generate_one(request)

    @modal.method()
    def generate_batch(self, requests:list[dict])->list[dict]:
        if not requests: return []
        if len(requests)>32: raise ValueError("single worker batch is limited to 32 items")
        return [self._generate_one(req) for req in requests]


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR:model_cache, REFERENCE_DIR:reference_cache}, scaledown_window=120, timeout=1200)
class FreeFrameProductionGenerator:
    """Bounded-production FLUX.2 Klein renderer used by Atlas-routed image jobs."""
    @modal.enter()
    def load(self):
        import torch
        from diffusers import DiffusionPipeline
        os.environ.setdefault("HF_HOME", CACHE_DIR); os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch=torch; self.model_name=PRODUCTION_MODEL
        self.pipe=DiffusionPipeline.from_pretrained(PRODUCTION_MODEL, torch_dtype=torch.bfloat16, cache_dir=CACHE_DIR).to("cuda")

    def _load_cached_reference_image(self, reference_id:str):
        from PIL import Image
        from modal_worker.reference_store import load_reference_bytes
        reference_cache.reload(); raw=load_reference_bytes(reference_id, REFERENCE_DIR)
        return Image.open(io.BytesIO(raw)).convert("RGB")

    def _generate_one(self, request:dict)->dict:
        started=time.monotonic(); spec=GenerationSpec.from_request(request); spec.validate()
        route=str(request.get("renderer_route","")).strip()
        if route != PRODUCTION_RENDERER_ROUTE: raise ValueError("production generator requires flux2_klein renderer_route")
        model_id=str(request.get("model_id","")).strip()
        if model_id != PRODUCTION_MODEL: raise ValueError("production request model_id does not match deployed production renderer")
        if spec.width % 16 or spec.height % 16: raise ValueError("FLUX.2 Klein dimensions must be divisible by 16")
        generator=self.torch.Generator(device="cuda").manual_seed(spec.seed)
        prompt=spec.prompt
        reference_metadata=None
        reference_id=str(request.get("reference_id","")).strip().lower()
        if reference_id:
            scale=float(request.get("reference_scale",0.35))
            if not 0.0 <= scale <= 1.0: raise ValueError("reference_scale must be between 0 and 1")
            if scale > 0:
                strength=_reference_strength_text(scale)
                prompt=(f"Use the supplied reference image {strength} as a visual reference while following the written production brief exactly. " + prompt)
                reference=self._load_cached_reference_image(reference_id)
                reference_metadata={"reference_id":reference_id,"reference_mode":request.get("reference_mode","style"),"requested_scale":scale,"scale_behavior":"prompt-steered-strength"}
        kwargs={"prompt":prompt,"width":spec.width,"height":spec.height,"num_inference_steps":spec.steps,"guidance_scale":spec.guidance_scale,"generator":generator}
        if reference_metadata is not None: kwargs["image"]=[reference]
        result=self.pipe(**kwargs).images[0]; payload=_png_payload(result)
        payload.update({"seed":spec.seed,"model":self.model_name,"renderer_route":PRODUCTION_RENDERER_ROUTE,"elapsed_seconds":round(time.monotonic()-started,3),"generation_spec":asdict(spec),"reference_conditioning":reference_metadata,"negative_prompt_applied":False,"bounded_production":True,"automatic_full_production_authorized":False}); return payload

    @modal.method()
    def generate(self, request:dict)->dict: return self._generate_one(request)

    @modal.method()
    def generate_batch(self, requests:list[dict])->list[dict]:
        if not requests: return []
        if len(requests)>32: raise ValueError("single production worker batch is limited to 32 items")
        return [self._generate_one(req) for req in requests]


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR:model_cache}, scaledown_window=120, timeout=900)
class FreeFrameExtractor:
    """Dedicated cached GPU subject extractor; isolated from generator VRAM state."""
    @modal.enter()
    def load(self):
        os.environ.setdefault("HF_HOME", CACHE_DIR); os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        from modal_worker.birefnet_extractor import BiRefNetExtractor
        self.extractor=BiRefNetExtractor()

    @modal.method()
    def extract(self, request: dict) -> dict:
        from modal_worker.extraction_provider import extract_and_validate
        encoded=request.get("image_base64")
        if not encoded: raise ValueError("image_base64 is required")
        source=base64.b64decode(encoded,validate=True)
        if len(source)>32*1024*1024: raise ValueError("image exceeds 32 MiB extraction limit")
        started=time.monotonic(); output_png,metadata=extract_and_validate(source, self.extractor)
        return {"mime_type":"image/png","image_base64":base64.b64encode(output_png).decode("ascii"),"bytes":len(output_png),"sha256":metadata["output_sha256"],"width":metadata["output_width"],"height":metadata["output_height"],"provider":metadata["extraction_provider"],"model":metadata["extraction_model"],"metadata":metadata,"elapsed_seconds":round(time.monotonic()-started,3)}


@app.function(image=image)
@modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
def health()->dict: return {"service":APP_NAME,"status":"ok","production_model":PRODUCTION_MODEL,"production_renderer_route":PRODUCTION_RENDERER_ROUTE,"legacy_model":LEGACY_MODEL,"gpu_profile":"L4","automatic_full_production_authorized":False}

@app.function(image=image, timeout=30)
@modal.fastapi_endpoint(method="GET", requires_proxy_auth=True)
def get_plushbound_brain()->dict:
    from modal_worker.plushbound_brain import brain_snapshot
    return brain_snapshot()

@app.function(image=image, timeout=30)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def plan_asset_job(request:dict)->dict:
    from modal_worker.atlas_controller import plan_asset
    return plan_asset(request)

@app.function(image=image, timeout=30)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def advance_atlas_record(request:dict)->dict:
    from modal_worker.atlas_production_ledger import AssetProductionRecord, transition
    record_data=request.get("record")
    if not isinstance(record_data,dict): raise ValueError("record must be an object")
    event=str(request.get("event","")).strip()
    if not event: raise ValueError("event is required")
    metadata=request.get("metadata")
    if metadata is not None and not isinstance(metadata,dict): raise ValueError("metadata must be an object")
    record=AssetProductionRecord.from_dict(record_data)
    transition(record,event,metadata)
    return record.to_dict()

@app.function(image=image, timeout=30)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def summarize_atlas_records(request:dict)->dict:
    from modal_worker.atlas_production_ledger import AssetProductionRecord, summarize
    raw=request.get("records")
    if not isinstance(raw,list): raise ValueError("records must be a list")
    return summarize([AssetProductionRecord.from_dict(item) for item in raw])

@app.function(image=image, timeout=30)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def record_atlas_visual_review(request:dict)->dict:
    from modal_worker.atlas_visual_gate import record_creature_visual_review
    return record_creature_visual_review(
        workflow_run_id=int(request.get("workflow_run_id",0)),
        head_sha=str(request.get("head_sha","")),
        artifact_digest=str(request.get("artifact_digest","")),
        canary_version=str(request.get("canary_version","")),
        judgments=request.get("judgments"),
    )

@app.function(image=image, timeout=30)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def validate_asset(request:dict)->dict:
    from PIL import Image
    from modal_worker.asset_profiles import validate_metadata
    encoded=request.get("image_base64")
    if not encoded: raise ValueError("image_base64 is required")
    raw=base64.b64decode(encoded,validate=True)
    if len(raw)>32*1024*1024: raise ValueError("image exceeds 32 MiB validation limit")
    with Image.open(io.BytesIO(raw)) as img: img.verify()
    with Image.open(io.BytesIO(raw)) as img: metadata={"format":img.format,"width":img.width,"height":img.height,"mode":img.mode,"has_alpha":"A" in img.getbands(),"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)}
    profile_name=request.get("profile"); profile_result=None
    if profile_name: profile_result=validate_metadata(profile_name=str(profile_name),fmt=str(metadata["format"] or ""),width=int(metadata["width"]),height=int(metadata["height"]),has_alpha=bool(metadata["has_alpha"]))
    return {"valid":profile_result["valid"] if profile_result else True,**metadata,"profile_validation":profile_result}

@app.function(image=image, volumes={REFERENCE_DIR:reference_cache}, timeout=30)
def store_reference_internal(request:dict)->dict:
    from modal_worker.reference_store import store_reference_bytes
    encoded=request.get("image_base64")
    if not encoded: raise ValueError("image_base64 is required")
    try: raw=base64.b64decode(str(encoded),validate=True)
    except Exception as exc: raise ValueError("image_base64 must be valid base64") from exc
    metadata=store_reference_bytes(raw,REFERENCE_DIR); reference_cache.commit(); return {"stored":True,**metadata.metadata()}

@app.function(image=image, timeout=30)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def store_reference(request:dict)->dict: return store_reference_internal.remote(request)

@app.function(image=image, timeout=1230)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def generate_image(request:dict)->dict:
    spec=GenerationSpec.from_request(request); spec.validate()
    route=str(request.get("renderer_route","")).strip()
    if route == PRODUCTION_RENDERER_ROUTE:
        return FreeFrameProductionGenerator().generate.remote(request)
    if route in ("", "legacy_sdxl"):
        return FreeFrameGenerator().generate.remote(request)
    raise ValueError(f"unknown FreeFrame renderer_route: {route}")

@app.function(image=image, timeout=930)
@modal.fastapi_endpoint(method="POST", requires_proxy_auth=True)
def extract_subject(request:dict)->dict:
    return FreeFrameExtractor().extract.remote(request)
