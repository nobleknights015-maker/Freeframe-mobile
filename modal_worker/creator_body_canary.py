"""Bounded real-GPU production canary for creator/body/001.

Produces one finished candidate creator body sheet at the locked 144x192 RGBA
3x4-48px geometry. This proves the body-layer subfamily only; it does not authorize
other creator slots or catalog-wide production.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path

import modal

APP_NAME = "freeframe-creator-body-canary"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUTPUT_PNG = "creator-body-001.png"
REFERENCE_PNG = "creator-body-001-reference.png"
REPORT_JSON = "creator-body-001-report.json"
CELL = 48
REFERENCE_SEED = 621001
BASE_SEED = 621010

DIRECTIONS = (
    ("down", "facing toward the viewer"),
    ("left", "facing left in profile"),
    ("right", "facing right in profile"),
    ("up", "facing away from the viewer"),
)
PHASES = (
    ("left-step", "left foot advanced in a small natural walking step"),
    ("idle", "neutral centered standing frame"),
    ("right-step", "right foot advanced in a small natural walking step"),
)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install("accelerate", "diffusers", "pillow>=10.4,<12", "safetensors", "sentencepiece", "torch>=2.6,<3", "transformers")
    .add_local_python_source("modal_worker")
)
app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


def identity_prompt() -> str:
    return (
        "single original adult Plushtopia character-creator base body, balanced natural adult proportions, "
        "bald head with no hair layer, neutral readable face, modest close-fitting neutral base underlayer only, "
        "no coat, no shirt layer, no pants layer, no skirt, no armor, no accessories, no jewelry, no weapons, "
        "full body visible from head to feet, centered, one person only, clean polished 2D fantasy JRPG game art, "
        "simple pure white background, no text, no border, no turnaround sheet, no extra figures, normal anatomy"
    )


def frame_prompt(direction_text: str, phase_text: str) -> str:
    return (
        "Preserve the exact same adult base-body identity, anatomy, proportions, skin appearance and neutral base underlayer from the reference. "
        "Do not add hair, clothing layers, accessories, armor, weapons, jewelry or props. "
        f"Render the same creator base as a compact JRPG movement sprite source, {direction_text}, {phase_text}, "
        "full body visible, centered, one person only, simple pure white background, no text, no border, normal anatomy."
    )


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=60, timeout=1200)
class CreatorBodyRunner:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import DiffusionPipeline
        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16, cache_dir=CACHE_DIR).to("cuda")

    def _generate(self, prompt: str, seed: int, reference=None):
        generator = self.torch.Generator(device="cuda").manual_seed(seed)
        kwargs = dict(prompt=prompt, width=512, height=512, guidance_scale=1.0, num_inference_steps=4, generator=generator)
        if reference is not None:
            kwargs["image"] = [reference]
        started = time.monotonic()
        result = self.pipe(**kwargs).images[0]
        return result, round(time.monotonic() - started, 3)

    @modal.method()
    def generate(self) -> dict:
        reference, ref_seconds = self._generate(identity_prompt(), REFERENCE_SEED)
        cells, frames, timings = [], [], []
        index = 0
        for direction, direction_text in DIRECTIONS:
            for phase, phase_text in PHASES:
                seed = BASE_SEED + index
                frame, elapsed = self._generate(frame_prompt(direction_text, phase_text), seed, reference)
                out = io.BytesIO(); frame.save(out, format="PNG")
                cells.append(base64.b64encode(out.getvalue()).decode("ascii"))
                frames.append({"index": index, "direction": direction, "phase": phase, "seed": seed})
                timings.append(elapsed)
                index += 1
        ref = io.BytesIO(); reference.save(ref, format="PNG")
        return {
            "model": MODEL_ID,
            "reference_png": base64.b64encode(ref.getvalue()).decode("ascii"),
            "reference_seconds": ref_seconds,
            "reference_seed": REFERENCE_SEED,
            "cells": cells,
            "frames": frames,
            "timings": timings,
        }


def _white_to_alpha(raw: bytes) -> bytes:
    from PIL import Image
    source = Image.open(io.BytesIO(raw)).convert("RGBA")
    data = []
    for r, g, b, _ in source.getdata():
        if r >= 245 and g >= 245 and b >= 245:
            data.append((r, g, b, 0))
        else:
            data.append((r, g, b, 255))
    source.putdata(data)
    out = io.BytesIO(); source.save(out, format="PNG")
    return out.getvalue()


@app.local_entrypoint()
def main():
    from modal_worker.production_factory import build_single_character
    from PIL import Image

    remote = CreatorBodyRunner().generate.remote()
    cleaned = [_white_to_alpha(base64.b64decode(value, validate=True)) for value in remote["cells"]]
    package = build_single_character(cleaned, cell_width=CELL, cell_height=CELL, padding=1)
    meta = package["metadata"]
    if (meta["width"], meta["height"]) != (144, 192):
        raise RuntimeError(f"creator body geometry mismatch: {meta['width']}x{meta['height']}")
    if meta["profile"] != "mv_single_character" or not meta["engine_validation"]["valid"] or not meta["has_alpha"]:
        raise RuntimeError(f"creator body engine validation failed: {meta}")

    Path(OUTPUT_PNG).write_bytes(package["png"])
    Path(REFERENCE_PNG).write_bytes(base64.b64decode(remote["reference_png"], validate=True))

    # Require visible alpha content in every locked 48x48 cell.
    with Image.open(OUTPUT_PNG) as sheet:
        rgba = sheet.convert("RGBA")
        occupied = []
        for row in range(4):
            for col in range(3):
                cell = rgba.crop((col*48, row*48, (col+1)*48, (row+1)*48)).getchannel("A")
                bbox = cell.getbbox()
                if bbox is None:
                    raise RuntimeError(f"creator body cell {row},{col} is empty")
                occupied.append(list(bbox))

    report = {
        "schema": "plushbound.creator_body_canary.v1",
        "status": "generated_pending_visual_review",
        "logical_id": "creator/body/001",
        "body_type": "balanced_neutral_adult_base",
        "model": remote["model"],
        "reference_conditioned": True,
        "reference_seed": remote["reference_seed"],
        "reference_seconds": remote["reference_seconds"],
        "source_frame_count": len(remote["cells"]),
        "generation_seconds": remote["timings"],
        "frame_manifest": remote["frames"],
        "sheet": meta,
        "cell_alpha_bboxes": occupied,
        "output_png": OUTPUT_PNG,
        "reference_png": REFERENCE_PNG,
        "catalog_wide_launch_authorized": False,
    }
    Path(REPORT_JSON).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k:v for k,v in report.items() if k not in {"frame_manifest", "generation_seconds", "cell_alpha_bboxes", "sheet"}}, sort_keys=True))
