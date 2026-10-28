"""Bounded paid source production for exactly one remaining Plushbound regional A5.

Hard limits:
- one explicit region per invocation;
- exactly eight 384x384 source masters;
- one generation attempt per material, no hidden retry spend;
- no cross-region work and no final A5 sheet generation;
- manual semantic/visual QA is mandatory before source closeout/compile.
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
from PIL import Image, ImageOps, ImageDraw

APP_NAME = "freeframe-tileset-regional-a5"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
OUTPUT_ROOT = Path("tileset-regional-a5")
EXPECTED_COUNT = 8
PROMPT_CONTRACT_VERSION = "regional-a5-material-swatch-v2"
VERSION = "plushbound-tileset-regional-a5-source-v2-material-swatch"

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


def stable_seed(region: str, asset_id: str) -> int:
    digest = hashlib.sha256(f"{VERSION}:{region}:{asset_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def load_assets(region: str) -> list[dict]:
    data = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
    if data["schema"] != "plushbound.tileset_regional_a5_scope_manifest.v1":
        raise RuntimeError("unexpected regional A5 scope schema")
    if region == "elyndor" or region not in data["remaining_regions"]:
        raise RuntimeError(f"paid regional A5 route refuses region: {region}")
    if data["spend_gate"]["catalog_wide_launch_authorized"] is not False:
        raise RuntimeError("catalog-wide launch unexpectedly authorized")
    if data["spend_gate"]["one_region_per_paid_trigger"] is not True:
        raise RuntimeError("one-region paid trigger safety changed")
    scope = data["regions"][region]
    if scope["status"] != "PREFLIGHT_PENDING" or scope["sheet_type"] != "A5":
        raise RuntimeError("full eight-source route requires a fresh PREFLIGHT_PENDING regional A5 scope; quarantined repairs must use the dedicated repair path")
    materials = scope["materials"]
    if len(materials) != EXPECTED_COUNT or len(set(materials)) != EXPECTED_COUNT:
        raise RuntimeError("regional A5 route requires exactly eight unique material keys")

    source = data["source_contract"]
    if source["generation_attempts_per_material_cap"] != 1:
        raise RuntimeError("generation attempt cap changed")
    if source.get("prompt_contract_version") != PROMPT_CONTRACT_VERSION:
        raise RuntimeError("regional A5 paid route requires repaired material-swatch prompt contract v2")
    region_hint = str(scope.get("region_material_hint", "")).strip()
    labels = scope.get("material_prompt_labels")
    if not region_hint:
        raise RuntimeError("region material hint is blank")
    if not isinstance(labels, dict) or set(labels) != set(materials):
        raise RuntimeError("material prompt labels do not exactly match the regional stable material scope")
    required_phrases = [str(x).lower() for x in source.get("required_prompt_phrases", [])]
    if not required_phrases:
        raise RuntimeError("anti-scene prompt phrase contract is missing")

    rows = []
    for material in materials:
        asset_id = f"tileset.{region}.a5.source.{material}"
        prompt = source["prompt_template"].format(
            region_material_hint=region_hint,
            material_name=labels[material],
        )
        if not all(phrase in prompt.lower() for phrase in required_phrases):
            raise RuntimeError(f"{asset_id}: rendered prompt does not satisfy anti-scene contract")
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
            "seed": stable_seed(region, asset_id),
        })
    if len({row["asset_id"] for row in rows}) != EXPECTED_COUNT:
        raise RuntimeError("duplicate regional A5 source stable ID")
    return rows


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=120,
    timeout=1200,
)
class RegionalA5Runner:
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

    def _render(self, request: dict) -> tuple[bytes, float]:
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
        elapsed = time.monotonic() - started
        out = io.BytesIO()
        result.save(out, format="PNG")
        return out.getvalue(), elapsed

    @modal.method()
    def run_region(self, rows: list[dict], region: str) -> dict:
        from modal_worker.production_inspector import inspect_generation
        from modal_worker.production_request_builder import build_production_request
        from modal_worker.tileset_source_normalizer import (
            MAX_EDGE_DISCONTINUITY,
            MIN_RGB_STDDEV,
            edge_discontinuity,
            normalize_image,
            rgb_stddev,
        )

        if len(rows) != EXPECTED_COUNT or {row["region"] for row in rows} != {region}:
            raise RuntimeError("remote regional A5 request is not exactly one eight-source region")
        if any(row.get("prompt_contract_version") != PROMPT_CONTRACT_VERSION for row in rows):
            raise RuntimeError("remote regional A5 request is not bound to prompt contract v2")
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

            raw, elapsed = self._render(request)
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
            norm_buf = io.BytesIO()
            normalized.save(norm_buf, format="PNG")
            norm_raw = norm_buf.getvalue()
            normalizer_accepted = edge <= MAX_EDGE_DISCONTINUITY and stddev >= MIN_RGB_STDDEV
            accepted = bool(inspection["accepted"]) and normalizer_accepted

            outputs.append({
                "asset_id": item["asset_id"],
                "material_key": item["material_key"],
                "region": region,
                "target_sheet_type": "A5",
                "preset": "plushbound_tileset_source",
                "model_id": MODEL_ID,
                "renderer_route": "flux2_klein",
                "prompt_contract_version": item["prompt_contract_version"],
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
                "maximum_edge_discontinuity": MAX_EDGE_DISCONTINUITY,
                "rgb_stddev": round(stddev, 4),
                "minimum_rgb_stddev": MIN_RGB_STDDEV,
                "normalizer_accepted": normalizer_accepted,
                "accepted": accepted,
                "quarantined": not accepted,
                "raw_png_base64": raw_payload["image_base64"],
                "normalized_png_base64": base64.b64encode(norm_raw).decode("ascii"),
            })

        accepted_count = sum(1 for row in outputs if row["accepted"])
        return {
            "schema": "plushbound.tileset_regional_a5_source_report.v1",
            "version": VERSION,
            "prompt_contract_version": PROMPT_CONTRACT_VERSION,
            "region": region,
            "target_sheet_type": "A5",
            "requested_count": EXPECTED_COUNT,
            "generation_count": EXPECTED_COUNT,
            "generation_retry_count": 0,
            "accepted_count": accepted_count,
            "quarantined_count": EXPECTED_COUNT - accepted_count,
            "total_gpu_seconds": round(total_gpu_seconds, 3),
            "wall_seconds": round(time.monotonic() - wall_started, 3),
            "model": MODEL_ID,
            "gpu": "L4",
            "bounded_production_authorized": True,
            "automatic_full_production_authorized": False,
            "catalog_wide_launch_authorized": False,
            "cross_region_generation_count": 0,
            "final_a5_generation_count": 0,
            "manual_visual_qa_required": True,
            "accepted_assets_must_be_protected_from_rerender": True,
            "outputs": outputs,
        }


def _contact_sheet(raw_paths: list[tuple[str, Path]], path: Path) -> None:
    cell = 384
    label_h = 28
    sheet = Image.new("RGBA", (cell * 4, (cell + label_h) * 2), (24, 24, 24, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (material, image_path) in enumerate(raw_paths):
        with Image.open(image_path) as im:
            tile = ImageOps.fit(im.convert("RGBA"), (cell, cell))
        x = (index % 4) * cell
        y = (index // 4) * (cell + label_h)
        sheet.alpha_composite(tile, (x, y))
        draw.text((x + 8, y + cell + 6), material, fill=(240, 240, 240, 255))
    sheet.save(path, format="PNG")


@app.local_entrypoint()
def main(region: str):
    rows = load_assets(region)
    report = RegionalA5Runner().run_region.remote(rows, region)
    out = OUTPUT_ROOT / region
    raw_dir = out / "raw"
    norm_dir = out / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    norm_dir.mkdir(parents=True, exist_ok=True)

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
        norm_path = norm_dir / f"{item['material_key']}-48.png"
        raw_path.write_bytes(raw)
        norm_path.write_bytes(normalized)
        item["raw_path"] = str(raw_path)
        item["normalized_path"] = str(norm_path)
        assets.append(item)
        contact_inputs.append((item["material_key"], raw_path))

    report["assets"] = assets
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    _contact_sheet(contact_inputs, out / "contact-sheet.png")
    print(json.dumps({k: v for k, v in report.items() if k != "assets"}, sort_keys=True))

    if report["generation_count"] != EXPECTED_COUNT or report["generation_retry_count"] != 0:
        raise RuntimeError("regional A5 generation count violated hard cap")
    if report["accepted_count"] != EXPECTED_COUNT or report["quarantined_count"] != 0:
        raise RuntimeError("regional A5 machine gate failed; region remains quarantined and must not be compiled")
