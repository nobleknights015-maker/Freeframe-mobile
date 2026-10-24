"""Max-mode NPC master -> MV single-character sheet production.

Consumes accepted NPC master PNGs from prior master-generation artifacts, uses each
master as the identity reference for twelve directional/movement frames, then
packages an exact 144x192 RGBA RPG-Maker-MV-compatible single-character sheet.

The preferred unified mode creates one Modal app and dispatches up to twelve
artifact+sublane lanes concurrently inside that app. This preserves Max Mode GPU
parallelism without tripping Modal AppCreate rate limits.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import modal

APP_NAME = "freeframe-mv-sheet-max-production"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
CELL_WIDTH = 48
CELL_HEIGHT = 48
SHEET_WIDTH = 144
SHEET_HEIGHT = 192
GPU_SECOND_COST_USD = 0.000222
MAX_ATTEMPTS = 2
MAX_PARALLEL_LANES = 12

DIRECTIONS = (
    ("down", "facing toward the viewer"),
    ("left", "facing left in profile"),
    ("right", "facing right in profile"),
    ("up", "facing away from the viewer"),
)
PHASES = (
    ("left-step", "left foot advanced, subtle walking motion"),
    ("idle", "neutral centered standing frame"),
    ("right-step", "right foot advanced, subtle walking motion"),
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


def _stable_seed(asset_name: str) -> int:
    value = int(hashlib.sha256(asset_name.encode("utf-8")).hexdigest()[:12], 16)
    return 100_000 + (value % 1_900_000_000)


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "lane"


def _frame_prompt(direction_text: str, phase_text: str) -> str:
    return (
        "Use the supplied reference image as the strict identity and costume reference. "
        "Preserve the exact same character identity, apparent age, face, hair, clothing design, "
        "colors, body proportions, equipment and regional visual identity. Ignore the reference background. "
        "Render that same original Plushbound character as a clean game sprite source, "
        f"{direction_text}, {phase_text}, full body visible from head to boots, centered, one character only, "
        "anatomically normal hands and limbs, no mutations, no extra fingers, no duplicate body parts, "
        "clean contemporary 2D JRPG game art, no turnaround sheet, no contact sheet, no text, no frame border, "
        "simple pure white background, strong readable silhouette"
    )


def _reference_bytes(path: Path) -> bytes:
    from PIL import Image

    source = Image.open(path).convert("RGB")
    source.thumbnail((512, 512), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (512, 512), "white")
    x = (512 - source.width) // 2
    y = (512 - source.height) // 2
    canvas.paste(source, (x, y))
    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


def _white_to_alpha(raw: bytes) -> bytes:
    from PIL import Image

    source = Image.open(io.BytesIO(raw)).convert("RGBA")
    pixels = []
    for r, g, b, _ in source.getdata():
        alpha = 0 if r >= 245 and g >= 245 and b >= 245 else 255
        pixels.append((r, g, b, alpha))
    source.putdata(pixels)
    out = io.BytesIO()
    source.save(out, format="PNG")
    return out.getvalue()


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=60,
    timeout=1800,
)
class SheetProductionRunner:
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
    def generate_cells(self, reference_png_b64: str, base_seed: int) -> dict:
        from PIL import Image

        reference = Image.open(io.BytesIO(base64.b64decode(reference_png_b64))).convert("RGB")
        encoded: list[str] = []
        timings: list[float] = []
        frame_meta: list[dict] = []
        index = 0
        for direction, direction_text in DIRECTIONS:
            for phase, phase_text in PHASES:
                seed = int(base_seed) + index
                generator = self.torch.Generator(device="cuda").manual_seed(seed)
                started = time.monotonic()
                result = self.pipe(
                    prompt=_frame_prompt(direction_text, phase_text),
                    image=[reference],
                    width=512,
                    height=512,
                    guidance_scale=1.0,
                    num_inference_steps=4,
                    generator=generator,
                ).images[0]
                elapsed = round(time.monotonic() - started, 3)
                out = io.BytesIO()
                result.save(out, format="PNG")
                encoded.append(base64.b64encode(out.getvalue()).decode("ascii"))
                timings.append(elapsed)
                frame_meta.append({
                    "index": index,
                    "direction": direction,
                    "phase": phase,
                    "seed": seed,
                })
                index += 1
        return {
            "model": MODEL_ID,
            "reference_conditioned": True,
            "cells": encoded,
            "frames": frame_meta,
            "timings": timings,
        }


def _build_sheet(master: Path, runner: SheetProductionRunner, out_dir: Path) -> dict:
    try:
        from .production_factory import build_single_character
    except ImportError:
        from production_factory import build_single_character

    base_seed = _stable_seed(master.stem)
    reference_raw = _reference_bytes(master)
    reference_b64 = base64.b64encode(reference_raw).decode("ascii")

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            remote = runner.generate_cells.remote(reference_b64, base_seed)
            cleaned = [_white_to_alpha(base64.b64decode(value)) for value in remote["cells"]]
            package = build_single_character(
                cleaned,
                cell_width=CELL_WIDTH,
                cell_height=CELL_HEIGHT,
                padding=1,
            )
            metadata = package["metadata"]
            if metadata["width"] != SHEET_WIDTH or metadata["height"] != SHEET_HEIGHT:
                raise RuntimeError(f"sheet size mismatch: {metadata['width']}x{metadata['height']}")
            if metadata["profile"] != "mv_single_character":
                raise RuntimeError("wrong editor asset profile")
            if not metadata["engine_validation"]["valid"]:
                raise RuntimeError(f"engine validation failed: {metadata['engine_validation']['errors']}")
            if not metadata["has_alpha"]:
                raise RuntimeError("sheet must retain alpha")
            if int(metadata.get("cell_count", 0)) != 12:
                raise RuntimeError("sheet must contain exactly 12 cells")

            output_name = f"${master.stem}.png"
            output_path = out_dir / output_name
            output_path.write_bytes(package["png"])
            gpu_seconds = round(sum(float(v) for v in remote["timings"]), 3)
            return {
                "accepted": True,
                "master_filename": master.name,
                "output_filename": output_name,
                "base_seed": base_seed,
                "attempt": attempt,
                "frame_manifest": remote["frames"],
                "generation_seconds": remote["timings"],
                "gpu_seconds": gpu_seconds,
                "estimated_generation_cost_usd": round(gpu_seconds * GPU_SECOND_COST_USD, 6),
                "sheet": metadata,
            }
        except Exception as exc:
            last_error = exc

    return {
        "accepted": False,
        "master_filename": master.name,
        "base_seed": base_seed,
        "attempts": MAX_ATTEMPTS,
        "error": f"{type(last_error).__name__}: {last_error}",
    }


def _find_masters(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("reg__*.png") if path.is_file()),
        key=lambda p: p.name,
    )


def _run_lane(
    *,
    root: Path,
    round_number: int,
    source_artifact: str,
    sublane: int,
    sublanes: int,
) -> dict:
    if sublanes < 1 or sublanes > 4:
        raise ValueError("sublanes must be between 1 and 4")
    if sublane < 0 or sublane >= sublanes:
        raise ValueError("sublane is outside the configured sublane count")

    masters = _find_masters(root)
    if not masters:
        raise RuntimeError(f"no accepted NPC master PNGs found below {root}")
    selected = masters[sublane::sublanes]
    if not selected:
        raise RuntimeError("sublane received no masters")

    lane_tag = f"{_safe(source_artifact)}__sublane-{sublane}"
    out_dir = Path("specialized-output") / f"npc-mv-round-{round_number:04d}" / lane_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    runner = SheetProductionRunner()
    items = [_build_sheet(master, runner, out_dir) for master in selected]
    accepted = [item for item in items if item.get("accepted")]
    quarantined = [item for item in items if not item.get("accepted")]
    gpu_seconds = round(sum(float(item.get("gpu_seconds", 0.0)) for item in accepted), 3)
    cost = round(sum(float(item.get("estimated_generation_cost_usd", 0.0)) for item in accepted), 6)

    report = {
        "version": "plushbound-specialized-npc-mv-max-v2-unified",
        "mode": "SPECIALIZED_MAX_SINGLE_APP_12_LANE",
        "round": int(round_number),
        "source_artifact": source_artifact,
        "sublane": int(sublane),
        "sublanes": int(sublanes),
        "source_master_count": len(masters),
        "selected_master_count": len(selected),
        "accepted": len(accepted),
        "quarantined": len(quarantined),
        "total_gpu_seconds": gpu_seconds,
        "estimated_generation_cost_usd": cost,
        "items": items,
        "production_authorized": True,
        "master_identity_preserved_by_reference": True,
        "editor_ready_geometry_required": True,
    }
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


@app.local_entrypoint()
def main(
    master_dir: str = "master-input",
    master_root: str = "",
    lane_specs_json: str = "",
    round_number: int = 1,
    source_artifact: str = "",
    sublane: int = 0,
    sublanes: int = 1,
    max_parallel: int = MAX_PARALLEL_LANES,
):
    if round_number < 1:
        raise ValueError("round_number must be >= 1")

    if lane_specs_json:
        specs = json.loads(lane_specs_json)
        if not isinstance(specs, list) or not specs:
            raise ValueError("lane_specs_json must be a non-empty JSON list")
        if len(specs) > MAX_PARALLEL_LANES:
            raise ValueError(f"at most {MAX_PARALLEL_LANES} lane specs are allowed")
        if max_parallel < 1 or max_parallel > MAX_PARALLEL_LANES:
            raise ValueError(f"max_parallel must be between 1 and {MAX_PARALLEL_LANES}")
        root = Path(master_root or master_dir)
        normalized = []
        seen = set()
        for raw in specs:
            artifact = str(raw["artifact"])
            lane = int(raw["sublane"])
            lane_count = int(raw.get("sublanes", 3))
            key = (artifact, lane, lane_count)
            if key in seen:
                raise ValueError(f"duplicate lane spec: {key}")
            seen.add(key)
            normalized.append((artifact, lane, lane_count))

        lane_reports = []
        failures = []
        with ThreadPoolExecutor(max_workers=min(max_parallel, len(normalized))) as pool:
            futures = {
                pool.submit(
                    _run_lane,
                    root=root / artifact,
                    round_number=round_number,
                    source_artifact=artifact,
                    sublane=lane,
                    sublanes=lane_count,
                ): (artifact, lane, lane_count)
                for artifact, lane, lane_count in normalized
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    lane_reports.append(future.result())
                except Exception as exc:
                    failures.append({"lane": key, "error": f"{type(exc).__name__}: {exc}"})

        lane_reports.sort(key=lambda r: (r["source_artifact"], r["sublane"]))
        accepted = sum(int(r.get("accepted", 0)) for r in lane_reports)
        quarantined = sum(int(r.get("quarantined", 0)) for r in lane_reports)
        cost = round(sum(float(r.get("estimated_generation_cost_usd", 0.0)) for r in lane_reports), 6)
        summary = {
            "version": "plushbound-specialized-npc-mv-unified-batch-v1",
            "mode": "SPECIALIZED_MAX_SINGLE_APP_12_LANE",
            "round": int(round_number),
            "requested_lanes": len(normalized),
            "completed_lane_reports": len(lane_reports),
            "lane_failures": failures,
            "accepted": accepted,
            "quarantined": quarantined,
            "estimated_generation_cost_usd": cost,
            "lane_reports": lane_reports,
        }
        batch_dir = Path("specialized-output") / f"npc-mv-round-{round_number:04d}"
        batch_dir.mkdir(parents=True, exist_ok=True)
        (batch_dir / "batch-report.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(summary, sort_keys=True))
        if failures or quarantined:
            raise RuntimeError(f"unified batch incomplete: lane_failures={len(failures)} quarantined={quarantined}")
        return

    report = _run_lane(
        root=Path(master_dir),
        round_number=round_number,
        source_artifact=source_artifact,
        sublane=sublane,
        sublanes=sublanes,
    )
    print(json.dumps(report, sort_keys=True))
    if report["quarantined"]:
        raise RuntimeError(f"{report['quarantined']} specialized NPC sheet(s) quarantined")
