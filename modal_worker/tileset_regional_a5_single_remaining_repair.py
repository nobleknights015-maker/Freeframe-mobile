"""Final one-source A5 repair after exactly seven regional sources are accepted.

This runner is intentionally narrow. It reads the locked 7/8 acceptance evidence,
constructs exactly the sole remaining stable source ID, and makes one generation
attempt. It cannot compile an A5 sheet or rerender any accepted source.
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

APP_NAME = "freeframe-tileset-regional-a5-single-remaining-repair"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
OUTPUT_ROOT = Path("tileset-regional-a5-single-remaining-repair")
PROMPT_CONTRACT_VERSION = "regional-a5-material-swatch-v2"
VERSION = "plushbound-regional-a5-single-remaining-repair-v1"
GPU_CANDIDATES = ["L4", "A10G"]
STARTUP_TIMEOUT_SECONDS = 180
REMOTE_TIMEOUT_SECONDS = 120
REED_REPAIR_CLAUSE = (
    " The woven reed material must continue beyond all four image edges as one infinite substrate. "
    "No mat object, no rug, no perimeter, no border, no stitched frame, no rectangular outline, "
    "no panel edge, no selvage edge, and no visible boundary around the weave. Use dense fine-scale "
    "interlaced reed fibers with moderate local tonal contrast and microtexture that remains readable "
    "after strong downsampling."
)

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
    digest = hashlib.sha256(f"{VERSION}:{asset_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def build_one(region: str) -> tuple[dict, dict]:
    scope = _load_json(SCOPE_PATH)
    if scope.get("schema") != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("unexpected A5 scope schema")
    regional = scope["regions"].get(region)
    if not regional or region == "elyndor":
        raise RuntimeError("unknown or closed region")
    if regional.get("status") != "REPAIR_PARTIAL_7_OF_8_ACCEPTED":
        raise RuntimeError("single remaining repair requires REPAIR_PARTIAL_7_OF_8_ACCEPTED")
    evidence_path = Path(str(regional.get("partial_acceptance_7_evidence", "")))
    partial = _load_json(evidence_path)
    if partial.get("schema") != "plushbound.tileset_regional_a5_partial_acceptance_7_of_8.v1":
        raise RuntimeError("unexpected 7/8 acceptance schema")
    if partial.get("status") != "PARTIAL_ACCEPTANCE_7_OF_8_REED_MATTING_ONLY_REMAINS":
        raise RuntimeError("7/8 evidence is not in the expected final-repair state")
    if partial.get("accepted_source_count") != 7 or partial.get("remaining_failed_source_count") != 1:
        raise RuntimeError("7/8 accounting drift")
    remaining = list(partial.get("remaining_failed_source_ids", []))
    if remaining != [f"tileset.{region}.a5.source.reed_matting"]:
        raise RuntimeError("single remaining repair refuses any ID other than locked reed_matting")
    accepted_ids = {row["asset_id"] for row in partial.get("accepted_sources", [])}
    if len(accepted_ids) != 7 or remaining[0] in accepted_ids:
        raise RuntimeError("accepted/remaining ID accounting drift")

    source = scope["source_contract"]
    if source.get("prompt_contract_version") != PROMPT_CONTRACT_VERSION:
        raise RuntimeError("prompt contract drift")
    if source.get("generation_attempts_per_material_cap") != 1:
        raise RuntimeError("generation attempt cap drift")
    materials = regional["materials"]
    labels = regional["material_prompt_labels"]
    if "reed_matting" not in materials or set(labels) != set(materials):
        raise RuntimeError("regional material scope drift")
    base = source["prompt_template"].format(
        region_material_hint=regional["region_material_hint"],
        material_name=labels["reed_matting"],
    )
    required = [str(x).lower() for x in source.get("required_prompt_phrases", [])]
    if not required or not all(p in base.lower() for p in required):
        raise RuntimeError("base anti-scene prompt contract incomplete")
    prompt = base + REED_REPAIR_CLAUSE
    asset_id = remaining[0]
    return ({
        "asset_id": asset_id,
        "material_key": "reed_matting",
        "region": region,
        "preset": "plushbound_tileset_source",
        "asset_class": "tileset_master",
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "repair_clause_sha256": hashlib.sha256(REED_REPAIR_CLAUSE.encode("utf-8")).hexdigest(),
        "seed": _seed(asset_id),
    }, {
        "partial_acceptance_path": str(evidence_path),
        "accepted_source_ids": sorted(accepted_ids),
    })


@app.cls(
    gpu=GPU_CANDIDATES,
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    startup_timeout=STARTUP_TIMEOUT_SECONDS,
    timeout=REMOTE_TIMEOUT_SECONDS,
)
class SingleRemainingRepairRunner:
    @modal.enter()
    def load(self):
        os.environ["HF_HOME"] = CACHE_DIR
        os.environ["HF_HUB_CACHE"] = f"{CACHE_DIR}/hub"
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        print("A5_SINGLE_REPAIR_STARTUP_STAGE=CONTAINER_STARTED", flush=True)
        print(f"A5_SINGLE_REPAIR_GPU_CANDIDATES={','.join(GPU_CANDIDATES)}", flush=True)
        print("A5_SINGLE_REPAIR_STARTUP_STAGE=CACHE_ONLY_MODEL_LOAD_BEGIN", flush=True)
        import torch
        from diffusers import DiffusionPipeline
        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
            cache_dir=CACHE_DIR,
            local_files_only=True,
        )
        print("A5_SINGLE_REPAIR_STARTUP_STAGE=PIPELINE_CPU_READY", flush=True)
        self.pipe.to("cuda")
        print("A5_SINGLE_REPAIR_STARTUP_STAGE=CUDA_READY", flush=True)

    @modal.method()
    def run_one(self, item: dict, accepted_source_ids: list[str]) -> dict:
        from modal_worker.production_inspector import inspect_generation
        from modal_worker.production_request_builder import build_production_request
        from modal_worker.tileset_source_normalizer import (
            MAX_EDGE_DISCONTINUITY,
            MIN_RGB_STDDEV,
            edge_discontinuity,
            normalize_image,
            rgb_stddev,
        )
        accepted = set(accepted_source_ids)
        if len(accepted) != 7 or item["asset_id"] in accepted:
            raise RuntimeError("single remaining repair accepted-ID exclusion failed")
        request = build_production_request(
            "plushbound_tileset_source", str(item["prompt"]), seed=int(item["seed"])
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
        }
        for key, value in expected.items():
            if request.get(key) != value:
                raise RuntimeError(f"{item['asset_id']}: invariant {key} drifted")
        generator = self.torch.Generator(device="cuda").manual_seed(int(request["seed"]))
        print(f"A5_SINGLE_REPAIR_RENDER_STAGE=BEGIN:{item['asset_id']}", flush=True)
        started = time.monotonic()
        result = self.pipe(
            prompt=str(request["prompt"]), width=384, height=384,
            guidance_scale=1.0, num_inference_steps=4, generator=generator,
        ).images[0]
        elapsed = time.monotonic() - started
        print(f"A5_SINGLE_REPAIR_RENDER_STAGE=IMAGE_READY:{elapsed:.3f}s", flush=True)
        buf = io.BytesIO(); result.save(buf, format="PNG"); raw = buf.getvalue()
        payload = {"image_base64": base64.b64encode(raw).decode("ascii"), "width":384, "height":384, "seed":int(request["seed"])}
        inspection = inspect_generation(item, payload)
        with Image.open(io.BytesIO(raw)) as generated:
            normalized = normalize_image(generated)
        edge = edge_discontinuity(normalized); stddev = rgb_stddev(normalized)
        nbuf = io.BytesIO(); normalized.save(nbuf, format="PNG"); norm = nbuf.getvalue()
        machine = bool(inspection["accepted"]) and edge <= MAX_EDGE_DISCONTINUITY and stddev >= MIN_RGB_STDDEV
        return {
            "schema":"plushbound.tileset_regional_a5_single_remaining_repair_report.v1",
            "version":VERSION,
            "region":item["region"], "asset_id":item["asset_id"], "material_key":item["material_key"],
            "prompt_contract_version":PROMPT_CONTRACT_VERSION,
            "prompt_sha256":item["prompt_sha256"], "repair_clause_sha256":item["repair_clause_sha256"],
            "generation_count":1, "generation_retry_count":0, "generation_attempts":1,
            "accepted_source_ids_excluded":sorted(accepted),
            "machine_accepted":machine, "manual_visual_qa_required":True,
            "raw_inspection":inspection, "source_size":[384,384], "normalized_size":[48,48],
            "raw_sha256":hashlib.sha256(raw).hexdigest(), "normalized_sha256":hashlib.sha256(norm).hexdigest(),
            "rgb_stddev":round(stddev,4), "minimum_rgb_stddev":MIN_RGB_STDDEV,
            "edge_discontinuity":round(edge,6), "maximum_edge_discontinuity":MAX_EDGE_DISCONTINUITY,
            "gpu":"L4_or_A10G", "gpu_candidates":GPU_CANDIDATES, "gpu_seconds":round(elapsed,3),
            "cross_region_generation_count":0, "final_a5_generation_count":0,
            "compile_authorized":False, "deterministic_finalize_authorized":False,
            "catalog_wide_launch_authorized":False, "runtime_import_proof":False,
            "raw_png_base64":payload["image_base64"], "normalized_png_base64":base64.b64encode(norm).decode("ascii"),
        }


@app.local_entrypoint()
def main(region: str):
    item, context = build_one(region)
    report = SingleRemainingRepairRunner().run_one.remote(item, context["accepted_source_ids"])
    out = OUTPUT_ROOT / region / item["material_key"]
    out.mkdir(parents=True, exist_ok=True)
    raw = base64.b64decode(report.pop("raw_png_base64")); norm = base64.b64decode(report.pop("normalized_png_base64"))
    raw_path = out / "reed_matting-384.png"; norm_path = out / "reed_matting-48.png"
    raw_path.write_bytes(raw); norm_path.write_bytes(norm)
    if hashlib.sha256(raw).hexdigest() != report["raw_sha256"] or hashlib.sha256(norm).hexdigest() != report["normalized_sha256"]:
        raise RuntimeError("single repair artifact hash mismatch")
    report["raw_path"] = str(raw_path); report["normalized_path"] = str(norm_path)
    report["partial_acceptance_path"] = context["partial_acceptance_path"]
    (out/"report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "raw_inspection"}, sort_keys=True))
    if not report["machine_accepted"]:
        raise RuntimeError("single remaining repair failed machine gate; do not compile")
