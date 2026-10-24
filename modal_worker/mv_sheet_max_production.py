"""Max-mode NPC master -> MV single-character sheet production.

Consumes accepted NPC master PNGs from prior master-generation artifacts, uses each
master as the identity reference for twelve directional/movement frames, then
packages an exact 144x192 RGBA RPG-Maker-MV-compatible single-character sheet.

One GitHub Actions lane handles one source artifact sublane. The workflow fans out
four source artifacts x three sublanes = twelve concurrent Modal L4 streams.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import time
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


@app.local_entrypoint()
def main(
    master_dir: str = "master-input",
    round_number: int = 1,
    source_artifact: str = "",
    sublane: int = 0,
    sublanes: int = 1,
):
    if round_number < 1:
        raise ValueError("round_number must be >= 1")
    if sublanes < 1 or sublanes > 4:
        raise ValueError("sublanes must be between 1 and 4")
    if sublane < 0 or sublane >= sublanes:
        raise ValueError("sublane is outside the configured sublane count")

    root = Path(master_dir)
    masters = _find_masters(root)
    if not masters:
        raise RuntimeError(f"no accepted NPC master PNGs found below {root}")
    selected = masters[sublane::sublanes]
    if not selected:
        raise RuntimeError("sublane received no masters")

    out_dir = Path("specialized-output") / f"npc-mv-round-{round_number:04d}" / f"lane-{sublane}"
    out_dir.mkdir(parents=True, exist_ok=True)

    runner = SheetProductionRunner()
    items = [_build_sheet(master, runner, out_dir) for master in selected]
    accepted = [item for item in items if item.get("accepted")]
    quarantined = [item for item in items if not item.get("accepted")]
    gpu_seconds = round(sum(float(item.get("gpu_seconds", 0.0)) for item in accepted), 3)
    cost = round(sum(float(item.get("estimated_generation_cost_usd", 0.0)) for item in accepted), 6)

    report = {
        "version": "plushbound-specialized-npc-mv-max-v1",
        "mode": "SPECIALIZED_MAX_12_STREAM",
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
    print(json.dumps(report, sort_keys=True))
    if quarantined:
        raise RuntimeError(f"{len(quarantined)} specialized NPC sheet(s) quarantined")
