"""Bounded repair of only the remaining failed A5 source IDs after a green one-source probe.

This route is deliberately unavailable until a one-source partial acceptance has
been banked and validated. It excludes accepted source IDs by construction and
never compiles a final A5 sheet.
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
from PIL import Image, ImageDraw, ImageOps

from modal_worker.tileset_regional_a5_partial_acceptance_validator import validate as validate_partial

APP_NAME = "freeframe-tileset-regional-a5-remaining-repair"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
OUTPUT_ROOT = Path("tileset-regional-a5-targeted-repair")
PROMPT_CONTRACT_VERSION = "regional-a5-material-swatch-v2"
VERSION = "plushbound-regional-a5-targeted-repair-v2-gpu-fallback-cache-only"
EXPECTED_ACCEPTED_BEFORE_REPAIR = 1
EXPECTED_REMAINING = 7
GPU_CANDIDATES = ["L4", "A10G"]
STARTUP_TIMEOUT_SECONDS = 180
REMOTE_TIMEOUT_SECONDS = 240

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
    digest = hashlib.sha256(f"{VERSION}:{PROMPT_CONTRACT_VERSION}:{asset_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def load_repair_rows(region: str) -> tuple[list[dict], dict]:
    scope = _load_json(SCOPE_PATH)
    if scope.get("schema") != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("unexpected regional A5 scope schema")
    if region == "elyndor" or region not in scope.get("remaining_regions", []):
        raise RuntimeError("remaining repair refuses closed or unknown region")
    if scope["spend_gate"]["catalog_wide_launch_authorized"] is not False:
        raise RuntimeError("catalog-wide launch unexpectedly authorized")
    if scope["spend_gate"]["one_region_per_paid_trigger"] is not True:
        raise RuntimeError("one-region paid trigger safety changed")

    regional = scope["regions"][region]
    if regional.get("status") != "REPAIR_PARTIAL_1_OF_8_ACCEPTED":
        raise RuntimeError("remaining repair requires REPAIR_PARTIAL_1_OF_8_ACCEPTED state")
    partial_path = Path(str(regional.get("partial_acceptance_evidence", "")))
    validation = validate_partial(partial_path, region)
    if validation.get("status") != "PASS_PARTIAL_ACCEPTANCE_PROBE_GREEN_1_OF_8":
        raise RuntimeError("partial acceptance validator did not pass")
    partial = _load_json(partial_path)
    if partial.get("accepted_source_count") != EXPECTED_ACCEPTED_BEFORE_REPAIR:
        raise RuntimeError("remaining repair expects exactly one accepted probe source")
    remaining_ids = list(partial.get("remaining_failed_source_ids", []))
    if len(remaining_ids) != EXPECTED_REMAINING or len(set(remaining_ids)) != EXPECTED_REMAINING:
        raise RuntimeError("remaining repair scope must be exactly seven unique failed source IDs")
    accepted_ids = set(partial.get("accepted_source_ids", []))
    if len(accepted_ids) != EXPECTED_ACCEPTED_BEFORE_REPAIR:
        raise RuntimeError("partial acceptance accepted-source accounting drift")
    if accepted_ids.intersection(remaining_ids):
        raise RuntimeError("remaining repair would rerender an accepted source")

    source = scope["source_contract"]
    if source.get("prompt_contract_version") != PROMPT_CONTRACT_VERSION:
        raise RuntimeError("remaining repair requires prompt contract v2")
    if source.get("generation_attempts_per_material_cap") != 1:
        raise RuntimeError("generation attempt cap drift")
    hint = str(regional.get("region_material_hint", "")).strip()
    materials = list(regional.get("materials", []))
    labels = regional.get("material_prompt_labels", {})
    if not hint or len(materials) != 8 or set(labels) != set(materials):
        raise RuntimeError("regional material prompt scope drift")
    expected_all_ids = {f"tileset.{region}.a5.source.{m}" for m in materials}
    if accepted_ids.union(remaining_ids) != expected_all_ids:
        raise RuntimeError("partial acceptance plus remaining repair IDs must account for exactly all eight regional source IDs")
    required_phrases = [str(x).lower() for x in source.get("required_prompt_phrases", [])]
    if not required_phrases:
        raise RuntimeError("anti-scene prompt contract is missing")

    rows = []
    prefix = f"tileset.{region}.a5.source."
    for asset_id in remaining_ids:
        if not asset_id.startswith(prefix):
            raise RuntimeError("remaining repair source ID is outside the target region")
        material = asset_id[len(prefix):]
        if material not in materials:
            raise RuntimeError("remaining repair material key is outside locked scope")
        prompt = source["prompt_template"].format(
            region_material_hint=hint,
            material_name=labels[material],
        )
        if not all(phrase in prompt.lower() for phrase in required_phrases):
            raise RuntimeError(f"{asset_id}: repaired prompt contract incomplete")
        rows.append({
            "asset_id": asset_id,
            "material_key": material,
            "region": region,
            "target_sheet_type": "A5",
            "preset": "plushbound_tileset_source",
            "asset_class": "tileset_master",
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_contract_version": PROMPT_CONTRACT_VERSION,
            "seed": _seed(asset_id),
        })
    if len(rows) != EXPECTED_REMAINING or accepted_ids.intersection({r["asset_id"] for r in rows}):
        raise RuntimeError("remaining repair row construction violated accepted-ID exclusion")
    context = {
        "partial_acceptance_path": str(partial_path),
        "accepted_source_ids": sorted(accepted_ids),
        "remaining_source_ids": [r["asset_id"] for r in rows],
    }
    return rows, context


@app.cls(
    gpu=GPU_CANDIDATES,
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    startup_timeout=STARTUP_TIMEOUT_SECONDS,
    timeout=REMOTE_TIMEOUT_SECONDS,
)
class RemainingRepairRunner:
    @modal.enter()
    def load(self):
        os.environ["HF_HOME"] = CACHE_DIR
        os.environ["HF_HUB_CACHE"] = f"{CACHE_DIR}/hub"
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        print("A5_REPAIR_STARTUP_STAGE=CONTAINER_STARTED", flush=True)
        print(f"A5_REPAIR_GPU_CANDIDATES={','.join(GPU_CANDIDATES)}", flush=True)
        print("A5_REPAIR_STARTUP_STAGE=CACHE_ONLY_MODEL_LOAD_BEGIN", flush=True)

        import torch
        from diffusers import DiffusionPipeline

        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
            cache_dir=CACHE_DIR,
            local_files_only=True,
        )
        print("A5_REPAIR_STARTUP_STAGE=PIPELINE_CPU_READY", flush=True)
        self.pipe.to("cuda")
        print("A5_REPAIR_STARTUP_STAGE=CUDA_READY", flush=True)

    def _render(self, request: dict, asset_id: str) -> tuple[bytes, float]:
        generator = self.torch.Generator(device="cuda").manual_seed(int(request["seed"]))
        print(f"A5_REPAIR_RENDER_STAGE=BEGIN:{asset_id}", flush=True)
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
        print(f"A5_REPAIR_RENDER_STAGE=IMAGE_READY:{asset_id}:{elapsed:.3f}s", flush=True)
        buffer = io.BytesIO()
        result.save(buffer, format="PNG")
        return buffer.getvalue(), elapsed

    @modal.method()
    def run_remaining(self, rows: list[dict], region: str, accepted_source_ids: list[str]) -> dict:
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
        if len(accepted) != EXPECTED_ACCEPTED_BEFORE_REPAIR:
            raise RuntimeError("remote remaining repair accepted-ID accounting drift")
        if len(rows) != EXPECTED_REMAINING or {row["region"] for row in rows} != {region}:
            raise RuntimeError("remote remaining repair is not exactly one seven-source region repair")
        if accepted.intersection({row["asset_id"] for row in rows}):
            raise RuntimeError("remote remaining repair includes an accepted source ID")
        if any(row.get("prompt_contract_version") != PROMPT_CONTRACT_VERSION for row in rows):
            raise RuntimeError("remote remaining repair prompt contract drift")

        outputs = []
        total_gpu_seconds = 0.0
        wall_started = time.monotonic()
        for item in rows:
            request = build_production_request(
                "plushbound_tileset_source",
                str(item["prompt"]),
                seed=int(item["seed"]),
            )
            invariants = {
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
            for key, expected in invariants.items():
                if request.get(key) != expected:
                    raise RuntimeError(f"{item['asset_id']}: invariant {key} drifted")

            raw, elapsed = self._render(request, item["asset_id"])
            total_gpu_seconds += elapsed
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
            norm_raw = norm_buffer.getvalue()
            normalizer_accepted = edge <= MAX_EDGE_DISCONTINUITY and stddev >= MIN_RGB_STDDEV
            machine_accepted = bool(inspection["accepted"]) and normalizer_accepted
            outputs.append({
                "asset_id": item["asset_id"],
                "material_key": item["material_key"],
                "region": region,
                "prompt_contract_version": PROMPT_CONTRACT_VERSION,
                "prompt_sha256": item["prompt_sha256"],
                "generation_attempts": 1,
                "seed": int(request["seed"]),
                "source_width": 384,
                "source_height": 384,
                "normalized_width": 48,
                "normalized_height": 48,
                "elapsed_seconds": round(elapsed, 3),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "normalized_sha256": hashlib.sha256(norm_raw).hexdigest(),
                "raw_inspection": inspection,
                "edge_discontinuity": round(edge, 6),
                "rgb_stddev": round(stddev, 4),
                "normalizer_accepted": normalizer_accepted,
                "machine_accepted": machine_accepted,
                "quarantined": not machine_accepted,
                "raw_png_base64": raw_payload["image_base64"],
                "normalized_png_base64": base64.b64encode(norm_raw).decode("ascii"),
            })

        accepted_count = sum(1 for row in outputs if row["machine_accepted"])
        return {
            "schema": "plushbound.tileset_regional_a5_remaining_repair_report.v1",
            "version": VERSION,
            "region": region,
            "target_sheet_type": "A5",
            "prompt_contract_version": PROMPT_CONTRACT_VERSION,
            "accepted_source_ids_excluded": sorted(accepted),
            "requested_count": EXPECTED_REMAINING,
            "generation_count": EXPECTED_REMAINING,
            "generation_retry_count": 0,
            "machine_accepted_count": accepted_count,
            "machine_quarantined_count": EXPECTED_REMAINING - accepted_count,
            "total_gpu_seconds": round(total_gpu_seconds, 3),
            "wall_seconds": round(time.monotonic() - wall_started, 3),
            "model": MODEL_ID,
            "gpu": "L4_or_A10G",
            "gpu_candidates": GPU_CANDIDATES,
            "startup_timeout_seconds": STARTUP_TIMEOUT_SECONDS,
            "remote_timeout_seconds": REMOTE_TIMEOUT_SECONDS,
            "cross_region_generation_count": 0,
            "final_a5_generation_count": 0,
            "compile_authorized": False,
            "deterministic_finalize_authorized": False,
            "catalog_wide_launch_authorized": False,
            "manual_visual_qa_required": True,
            "outputs": outputs,
        }


def _contact_sheet(raw_paths: list[tuple[str, Path]], path: Path) -> None:
    cell = 384
    label_h = 28
    columns = 4
    rows = 2
    sheet = Image.new("RGBA", (cell * columns, (cell + label_h) * rows), (24, 24, 24, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (material, image_path) in enumerate(raw_paths):
        with Image.open(image_path) as im:
            tile = ImageOps.fit(im.convert("RGBA"), (cell, cell))
        x = (index % columns) * cell
        y = (index // columns) * (cell + label_h)
        sheet.alpha_composite(tile, (x, y))
        draw.text((x + 8, y + cell + 6), material, fill=(240, 240, 240, 255))
    sheet.save(path, format="PNG")


@app.local_entrypoint()
def main(region: str):
    rows, context = load_repair_rows(region)
    report = RemainingRepairRunner().run_remaining.remote(rows, region, context["accepted_source_ids"])
    out = OUTPUT_ROOT / region
    raw_dir = out / "raw"
    normalized_dir = out / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    assets = []
    contact_inputs = []
    for item in report.pop("outputs"):
        raw = base64.b64decode(item.pop("raw_png_base64"))
        normalized = base64.b64decode(item.pop("normalized_png_base64"))
        if hashlib.sha256(raw).hexdigest() != item["raw_sha256"]:
            raise RuntimeError(f"{item['asset_id']}: raw artifact hash mismatch")
        if hashlib.sha256(normalized).hexdigest() != item["normalized_sha256"]:
            raise RuntimeError(f"{item['asset_id']}: normalized artifact hash mismatch")
        raw_path = raw_dir / f"{item['material_key']}-384.png"
        normalized_path = normalized_dir / f"{item['material_key']}-48.png"
        raw_path.write_bytes(raw)
        normalized_path.write_bytes(normalized)
        item["raw_path"] = str(raw_path)
        item["normalized_path"] = str(normalized_path)
        assets.append(item)
        contact_inputs.append((item["material_key"], raw_path))

    report["partial_acceptance_path"] = context["partial_acceptance_path"]
    report["assets"] = assets
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    _contact_sheet(contact_inputs, out / "contact-sheet-remaining-seven.png")
    print(json.dumps({k: v for k, v in report.items() if k != "assets"}, sort_keys=True))

    if report["generation_count"] != EXPECTED_REMAINING or report["generation_retry_count"] != 0:
        raise RuntimeError("remaining repair generation count violated hard cap")
    if report["machine_accepted_count"] != EXPECTED_REMAINING or report["machine_quarantined_count"] != 0:
        raise RuntimeError("remaining repair machine gate failed; do not combine or compile")
