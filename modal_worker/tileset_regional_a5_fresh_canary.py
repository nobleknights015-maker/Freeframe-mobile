"""One-source paid canary for the safest fresh Plushbound regional A5 source.

This route is deliberately smaller than the eight-source regional producer:
- one fresh PREFLIGHT_PENDING region only;
- one exact stable source ID only;
- one generation attempt only;
- no cross-region generation;
- no remaining-seven continuation;
- no final A5 compile/finalize;
- mandatory manual semantic/visual QA before any source is banked.
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
from PIL import Image

APP_NAME = "freeframe-tileset-regional-a5-fresh-canary"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
READINESS_PATH = Path("modal_worker/tileset_regional_a5_semantic_readiness_2026-10-28.json")
OUTPUT_ROOT = Path("tileset-regional-a5-fresh-canary")
PROMPT_CONTRACT_VERSION = "regional-a5-material-swatch-v2"
CANARY_VERSION = "plushbound-regional-a5-fresh-canary-v1"

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


def _load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing required evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _seed(asset_id: str) -> int:
    digest = hashlib.sha256(f"{CANARY_VERSION}:{asset_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def build_canary(region: str, asset_id: str) -> dict:
    scope = _load(SCOPE_PATH)
    readiness = _load(READINESS_PATH)
    if scope.get("schema") != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("unexpected regional A5 scope schema")
    if readiness.get("schema") != "plushbound.tileset_regional_a5_semantic_readiness.v1":
        raise RuntimeError("unexpected semantic readiness schema")
    if region == "elyndor" or region not in scope.get("remaining_regions", []):
        raise RuntimeError("fresh canary refuses closed or unknown region")
    if scope["spend_gate"]["catalog_wide_launch_authorized"] is not False:
        raise RuntimeError("catalog-wide launch unexpectedly authorized")
    if scope["spend_gate"]["one_region_per_paid_trigger"] is not True:
        raise RuntimeError("one-region paid trigger safety changed")
    if scope["spend_gate"]["never_stack_paid_runs"] is not True:
        raise RuntimeError("paid-run stacking lock changed")

    regional = scope["regions"][region]
    if regional.get("status") != "PREFLIGHT_PENDING":
        raise RuntimeError("fresh canary requires a fresh PREFLIGHT_PENDING region")
    if regional.get("stable_sheet_id") != f"tileset.{region}.a5":
        raise RuntimeError("regional stable sheet ID drift")

    priorities = {row["region"]: row for row in readiness.get("fresh_region_priority", [])}
    ranked = priorities.get(region)
    if not ranked:
        raise RuntimeError("region lacks semantic readiness ranking")
    if ranked.get("priority") != 1 or ranked.get("risk") != "low":
        raise RuntimeError("fresh canary only permits current priority-1 low-risk region")
    if readiness.get("next_fresh_paid_candidate_after_shared_paid_lane_is_clear") != region:
        raise RuntimeError("fresh paid candidate changed in semantic readiness evidence")

    prefix = f"tileset.{region}.a5.source."
    if not asset_id.startswith(prefix):
        raise RuntimeError("canary stable source ID does not belong to target region")
    material = asset_id[len(prefix):]
    materials = regional.get("materials", [])
    labels = regional.get("material_prompt_labels", {})
    if material not in materials or set(labels) != set(materials):
        raise RuntimeError("canary material is outside locked stable source scope")
    if material in set(ranked.get("watch_items", [])):
        raise RuntimeError("fresh canary refuses a semantic watch-item source")

    source = scope["source_contract"]
    if source.get("prompt_contract_version") != PROMPT_CONTRACT_VERSION:
        raise RuntimeError("prompt contract is not repaired material-swatch v2")
    if source.get("generation_attempts_per_material_cap") != 1:
        raise RuntimeError("generation attempt cap drift")
    hint = str(regional.get("region_material_hint", "")).strip()
    prompt = str(source["prompt_template"]).format(
        region_material_hint=hint,
        material_name=labels[material],
    )
    required = [str(x).lower() for x in source.get("required_prompt_phrases", [])]
    if not required or not all(phrase in prompt.lower() for phrase in required):
        raise RuntimeError("rendered fresh-canary prompt fails anti-scene contract")

    return {
        "region": region,
        "asset_id": asset_id,
        "material_key": material,
        "preset": "plushbound_tileset_source",
        "asset_class": "tileset_master",
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "semantic_priority": ranked["priority"],
        "semantic_risk": ranked["risk"],
        "seed": _seed(asset_id),
    }


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    timeout=420,
)
class FreshCanaryRunner:
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
    def run_one(self, item: dict) -> dict:
        from modal_worker.production_inspector import inspect_generation
        from modal_worker.production_request_builder import build_production_request
        from modal_worker.tileset_source_normalizer import (
            MAX_EDGE_DISCONTINUITY,
            MIN_RGB_STDDEV,
            edge_discontinuity,
            normalize_image,
            rgb_stddev,
        )

        request = build_production_request(
            "plushbound_tileset_source",
            str(item["prompt"]),
            seed=int(item["seed"]),
        )
        expected = {
            "model_id": MODEL_ID,
            "renderer_route": "flux2_klein",
            "width": 384,
            "height": 384,
            "steps": 4,
            "guidance_scale": 1.0,
            "bounded_production_authorized": True,
            "automatic_full_production_authorized": False,
            "catalog_wide_launch_authorized": False,
            "production_style_validated": True,
            "production_style_profile": "plushbound_tileset_source",
            "style_preset": "plushbound_tileset_source",
        }
        for key, expected_value in expected.items():
            if request.get(key) != expected_value:
                raise RuntimeError(f"{item['asset_id']}: invariant {key} drifted")

        generator = self.torch.Generator(device="cuda").manual_seed(int(request["seed"]))
        started = time.monotonic()
        result = self.pipe(
            prompt=str(request["prompt"]),
            width=384,
            height=384,
            guidance_scale=1.0,
            num_inference_steps=4,
            generator=generator,
        ).images[0]
        elapsed = time.monotonic() - started
        raw_buffer = io.BytesIO()
        result.save(raw_buffer, format="PNG")
        raw = raw_buffer.getvalue()

        raw_payload = {
            "image_base64": base64.b64encode(raw).decode("ascii"),
            "width": 384,
            "height": 384,
            "seed": int(request["seed"]),
        }
        inspection = inspect_generation(item, raw_payload)
        with Image.open(io.BytesIO(raw)) as generated:
            normalized = normalize_image(generated)
        edge = edge_discontinuity(normalized)
        stddev = rgb_stddev(normalized)
        norm_buffer = io.BytesIO()
        normalized.save(norm_buffer, format="PNG")
        normalized_raw = norm_buffer.getvalue()
        normalizer_accepted = edge <= MAX_EDGE_DISCONTINUITY and stddev >= MIN_RGB_STDDEV
        machine_accepted = bool(inspection["accepted"]) and normalizer_accepted

        return {
            "schema": "plushbound.tileset_regional_a5_fresh_canary_report.v1",
            "version": CANARY_VERSION,
            "status": "MACHINE_PASS_MANUAL_VISUAL_REQUIRED" if machine_accepted else "MACHINE_FAIL_QUARANTINED",
            "region": item["region"],
            "asset_id": item["asset_id"],
            "material_key": item["material_key"],
            "target_sheet_type": "A5",
            "stable_sheet_id": f"tileset.{item['region']}.a5",
            "prompt_contract_version": item["prompt_contract_version"],
            "prompt_sha256": item["prompt_sha256"],
            "semantic_priority": item["semantic_priority"],
            "semantic_risk": item["semantic_risk"],
            "generation_count": 1,
            "generation_retry_count": 0,
            "cross_region_generation_count": 0,
            "remaining_seven_generation_count": 0,
            "final_a5_generation_count": 0,
            "compile_authorized": False,
            "deterministic_finalize_authorized": False,
            "automatic_remaining_seven_authorized": False,
            "catalog_wide_launch_authorized": False,
            "manual_visual_qa_required": True,
            "machine_accepted": machine_accepted,
            "quarantined": not machine_accepted,
            "model": MODEL_ID,
            "gpu": "L4",
            "gpu_seconds": round(elapsed, 3),
            "generation_attempts": 1,
            "seed": int(request["seed"]),
            "source_size": [384, 384],
            "normalized_size": [48, 48],
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "normalized_sha256": hashlib.sha256(normalized_raw).hexdigest(),
            "edge_discontinuity": round(edge, 6),
            "rgb_stddev": round(stddev, 4),
            "raw_inspection": inspection,
            "raw_png_base64": raw_payload["image_base64"],
            "normalized_png_base64": base64.b64encode(normalized_raw).decode("ascii"),
        }


@app.local_entrypoint()
def main(region: str, asset_id: str):
    item = build_canary(region, asset_id)
    report = FreshCanaryRunner().run_one.remote(item)

    out = OUTPUT_ROOT / region / item["material_key"]
    out.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(report.pop("raw_png_base64"))
    normalized = base64.b64decode(report.pop("normalized_png_base64"))
    raw_path = out / f"{item['material_key']}-384.png"
    normalized_path = out / f"{item['material_key']}-48.png"
    raw_path.write_bytes(raw)
    normalized_path.write_bytes(normalized)
    if hashlib.sha256(raw).hexdigest() != report["raw_sha256"]:
        raise RuntimeError("fresh canary raw artifact hash mismatch")
    if hashlib.sha256(normalized).hexdigest() != report["normalized_sha256"]:
        raise RuntimeError("fresh canary normalized artifact hash mismatch")
    report["raw_path"] = str(raw_path)
    report["normalized_path"] = str(normalized_path)
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "raw_inspection"}, sort_keys=True))
    if not report["machine_accepted"]:
        raise RuntimeError("fresh one-source canary failed machine gate; do not generate remaining regional sources")
