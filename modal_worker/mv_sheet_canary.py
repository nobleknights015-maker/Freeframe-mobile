"""Bounded real-GPU canary for one editor-ready 3x4 Plushbound character sheet.

The diffusion model generates twelve independent source frames on a near-white
background.  The local entrypoint converts that background to alpha, then sends
all twelve cells through the real production factory.  Success requires the final
$ sheet to be exactly 144x192 RGBA PNG (48x48 cells) and engine-valid.

This is a capability canary, not authorization for the 22k production run.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time

import modal

APP_NAME = "freeframe-mv-sheet-canary"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUTPUT_PNG = "$plushbound_sheet_canary.png"
CELL_WIDTH = 48
CELL_HEIGHT = 48
SHEET_WIDTH = 144
SHEET_HEIGHT = 192

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


def frame_prompt(direction_text: str, phase_text: str) -> str:
    return (
        "single original Plushbound fantasy adventurer game sprite source, same adult adventurer identity in every frame, "
        "short dark travel coat, tan leather satchel, practical boots, clean contemporary 2D JRPG game art, "
        f"{direction_text}, {phase_text}, full body visible, centered, one character only, no extra figures, "
        "no turnaround sheet, no contact sheet, no text, no frame border, simple pure white background, strong readable silhouette"
    )


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=60,
    timeout=1200,
)
class SheetCanaryRunner:
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
    def generate_cells(self) -> dict:
        encoded: list[str] = []
        timings: list[float] = []
        frame_meta: list[dict] = []
        base_seed = 18420
        index = 0
        for direction, direction_text in DIRECTIONS:
            for phase, phase_text in PHASES:
                seed = base_seed + index
                generator = self.torch.Generator(device="cuda").manual_seed(seed)
                started = time.monotonic()
                result = self.pipe(
                    prompt=frame_prompt(direction_text, phase_text),
                    width=512,
                    height=512,
                    guidance_scale=1.0,
                    num_inference_steps=4,
                    generator=generator,
                ).images[0]
                timings.append(round(time.monotonic() - started, 3))
                out = io.BytesIO()
                result.save(out, format="PNG")
                encoded.append(base64.b64encode(out.getvalue()).decode("ascii"))
                frame_meta.append({"index": index, "direction": direction, "phase": phase, "seed": seed})
                index += 1
        return {
            "model": MODEL_ID,
            "cells": encoded,
            "frames": frame_meta,
            "timings": timings,
            "production_authorized": False,
        }


def _white_to_alpha(raw: bytes) -> bytes:
    from PIL import Image

    source = Image.open(io.BytesIO(raw)).convert("RGBA")
    pixels = []
    for r, g, b, _ in source.getdata():
        # Conservative near-white key. Soft off-white fringe stays partially visible
        # and is then cropped/normalized by the production factory.
        alpha = 0 if r >= 245 and g >= 245 and b >= 245 else 255
        pixels.append((r, g, b, alpha))
    source.putdata(pixels)
    out = io.BytesIO()
    source.save(out, format="PNG")
    return out.getvalue()


@app.local_entrypoint()
def main():
    from production_factory import build_single_character

    remote = SheetCanaryRunner().generate_cells.remote()
    cleaned = [_white_to_alpha(base64.b64decode(value)) for value in remote["cells"]]
    package = build_single_character(cleaned, cell_width=CELL_WIDTH, cell_height=CELL_HEIGHT, padding=1)
    metadata = package["metadata"]
    if metadata["width"] != SHEET_WIDTH or metadata["height"] != SHEET_HEIGHT:
        raise RuntimeError(f"editor sheet size mismatch: {metadata['width']}x{metadata['height']}")
    if metadata["profile"] != "mv_single_character":
        raise RuntimeError("wrong editor asset profile")
    if not metadata["engine_validation"]["valid"]:
        raise RuntimeError("editor validation did not pass")
    if not metadata["has_alpha"]:
        raise RuntimeError("editor sheet must retain alpha")

    with open(OUTPUT_PNG, "wb") as handle:
        handle.write(package["png"])

    report = {
        "version": "plushbound-mv-sheet-canary-v1",
        "model": remote["model"],
        "source_frame_count": len(remote["cells"]),
        "frame_manifest": remote["frames"],
        "generation_seconds": remote["timings"],
        "sheet": metadata,
        "output_png": OUTPUT_PNG,
        "editor_ready_geometry": True,
        "production_authorized": False,
    }
    print(json.dumps(report, sort_keys=True))
