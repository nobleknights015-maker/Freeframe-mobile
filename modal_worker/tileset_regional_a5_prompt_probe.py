"""One-source paid prompt-repair probe for a quarantined regional A5 source.

This is intentionally smaller than the regional producer. It renders exactly one
previously failed source ID after a repaired no-spend prompt contract passes.
No retries, no second source, no compile and no cross-region work are permitted.
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

APP_NAME = "freeframe-tileset-regional-a5-prompt-probe"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
OUTPUT_ROOT = Path("tileset-regional-a5-prompt-probe")
PROMPT_CONTRACT_VERSION = "regional-a5-material-swatch-v2"
PROBE_VERSION = "plushbound-regional-a5-prompt-probe-v1"
REMOTE_TIMEOUT_SECONDS = 420

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


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing required evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _seed(asset_id: str) -> int:
    digest = hashlib.sha256(f"{PROMPT_CONTRACT_VERSION}:{asset_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def build_probe(region: str, asset_id: str) -> dict:
    scope = _load_json(SCOPE_PATH)
    if scope.get("schema") != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("unexpected regional A5 scope schema")
    if region == "elyndor" or region not in scope.get("remaining_regions", []):
        raise RuntimeError("probe refuses closed or unknown region")
    if scope["spend_gate"]["catalog_wide_launch_authorized"] is not False:
        raise RuntimeError("catalog-wide launch unexpectedly authorized")
    if scope["spend_gate"]["one_region_per_paid_trigger"] is not True:
        raise RuntimeError("one-region paid trigger safety changed")

    regional = scope["regions"][region]
    if regional.get("status") != "QUARANTINED_PROMPT_REPAIR_REQUIRED":
        raise RuntimeError("one-source probe requires a quarantined prompt-repair region")
    if regional.get("stable_sheet_id") != f"tileset.{region}.a5":
        raise RuntimeError("regional stable sheet ID drift")

    quarantine_path = Path(str(regional.get("quarantine_evidence", "")))
    quarantine = _load_json(quarantine_path)
    if quarantine.get("schema") != "plushbound.tileset_regional_a5_source_quarantine.v1":
        raise RuntimeError("unexpected quarantine schema")
    if quarantine.get("status") != "QUARANTINED_MANUAL_VISUAL_FAIL_0_OF_8_ACCEPTED":
        raise RuntimeError("quarantine is not the expected 0/8 scene-drift failure")
    if quarantine.get("region") != region or quarantine.get("target_sheet_type") != "A5":
        raise RuntimeError("quarantine target mismatch")
    if quarantine.get("accepted_source_count") != 0 or quarantine.get("quarantined_source_count") != 8:
        raise RuntimeError("quarantine accounting drift")
    if quarantine.get("compile_authorized") is not False or quarantine.get("deterministic_finalize_authorized") is not False:
        raise RuntimeError("quarantine unexpectedly authorizes compile/finalize")
    failed_ids = set(quarantine["rerender_authority"]["failed_source_ids"])
    if asset_id not in failed_ids:
        raise RuntimeError("probe asset ID is not authorized by quarantine failure evidence")

    prefix = f"tileset.{region}.a5.source."
    if not asset_id.startswith(prefix):
        raise RuntimeError("probe asset stable ID does not belong to target region")
    material_key = asset_id[len(prefix):]
    materials = regional.get("materials", [])
    if material_key not in materials:
        raise RuntimeError("probe material key is not in locked regional scope")
    labels = regional.get("material_prompt_labels", {})
    if set(labels) != set(materials):
        raise RuntimeError("material prompt label map does not match stable source scope")

    source_contract = scope["source_contract"]
    if source_contract.get("prompt_contract_version") != PROMPT_CONTRACT_VERSION:
        raise RuntimeError("prompt contract version is not the repaired v2 contract")
    if source_contract.get("generation_attempts_per_material_cap") != 1:
        raise RuntimeError("generation attempt cap drift")
    hint = str(regional.get("region_material_hint", "")).strip()
    prompt = str(source_contract["prompt_template"]).format(
        region_material_hint=hint,
        material_name=labels[material_key],
    )
    prompt_lower = prompt.lower()
    required = [str(x).lower() for x in source_contract.get("required_prompt_phrases", [])]
    if not required or not all(phrase in prompt_lower for phrase in required):
        raise RuntimeError("rendered prompt does not satisfy repaired anti-scene contract")

    prior = next((row for row in quarantine.get("sources", []) if row.get("asset_id") == asset_id), None)
    if prior is None:
        raise RuntimeError("quarantine lacks prior source record")
    return {
        "region": region,
        "asset_id": asset_id,
        "material_key": material_key,
        "preset": "plushbound_tileset_source",
        "asset_class": "tileset_master",
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "seed": _seed(asset_id),
        "prior_failed_run_id": quarantine["source_run_id"],
        "prior_failed_raw_sha256": prior["raw_sha256"],
        "prior_failed_normalized_sha256": prior["normalized_sha256"],
        "prior_failed_manual_visual_status": prior["manual_visual_status"],
        "quarantine_path": str(quarantine_path),
    }


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    timeout=REMOTE_TIMEOUT_SECONDS,
)
class PromptProbeRunner:
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
            "schema": "plushbound.tileset_regional_a5_prompt_probe_report.v1",
            "version": PROBE_VERSION,
            "status": "MACHINE_PASS_MANUAL_VISUAL_REQUIRED" if machine_accepted else "MACHINE_FAIL_QUARANTINED",
            "region": item["region"],
            "asset_id": item["asset_id"],
            "material_key": item["material_key"],
            "target_sheet_type": "A5",
            "stable_sheet_id": f"tileset.{item['region']}.a5",
            "prompt_contract_version": item["prompt_contract_version"],
            "prompt_sha256": item["prompt_sha256"],
            "generation_count": 1,
            "generation_retry_count": 0,
            "cross_region_generation_count": 0,
            "final_a5_generation_count": 0,
            "compile_authorized": False,
            "deterministic_finalize_authorized": False,
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
            "prior_failed_run_id": item["prior_failed_run_id"],
            "prior_failed_raw_sha256": item["prior_failed_raw_sha256"],
            "prior_failed_normalized_sha256": item["prior_failed_normalized_sha256"],
            "prior_failed_manual_visual_status": item["prior_failed_manual_visual_status"],
            "quarantine_path": item["quarantine_path"],
            "raw_png_base64": raw_payload["image_base64"],
            "normalized_png_base64": base64.b64encode(normalized_raw).decode("ascii"),
        }


@app.local_entrypoint()
def main(region: str, asset_id: str):
    item = build_probe(region, asset_id)
    report = PromptProbeRunner().run_one.remote(item)

    out = OUTPUT_ROOT / region / item["material_key"]
    out.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(report.pop("raw_png_base64"))
    normalized = base64.b64decode(report.pop("normalized_png_base64"))
    raw_path = out / f"{item['material_key']}-384.png"
    normalized_path = out / f"{item['material_key']}-48.png"
    raw_path.write_bytes(raw)
    normalized_path.write_bytes(normalized)
    if hashlib.sha256(raw).hexdigest() != report["raw_sha256"]:
        raise RuntimeError("prompt probe raw artifact hash mismatch")
    if hashlib.sha256(normalized).hexdigest() != report["normalized_sha256"]:
        raise RuntimeError("prompt probe normalized artifact hash mismatch")
    report["raw_path"] = str(raw_path)
    report["normalized_path"] = str(normalized_path)
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "raw_inspection"}, sort_keys=True))
    if not report["machine_accepted"]:
        raise RuntimeError("one-source prompt repair probe failed machine gate; do not spend on further sources")
