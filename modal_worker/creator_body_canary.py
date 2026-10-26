"""Bounded real-GPU production canary for creator/body/001.

Produces one finished candidate creator body sheet at the locked 144x192 RGBA
3x4-48px geometry. Round 2 replaces crude white-threshold cleanup with the deployed
BiRefNet extraction worker and rejects exaggerated walk-cycle silhouettes.
This proves the body-layer subfamily only; it does not authorize other creator slots
or catalog-wide production.
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
WORKER_APP = "freeframe-worker"
EXTRACTOR_CLASS = "FreeFrameExtractor"
OUTPUT_PNG = "creator-body-001.png"
REFERENCE_PNG = "creator-body-001-reference.png"
REPORT_JSON = "creator-body-001-report.json"
CELL = 48
REFERENCE_SEED = 621001
BASE_SEED = 621110

DIRECTIONS = (
    ("down", "facing toward the viewer"),
    ("left", "facing left in profile"),
    ("right", "facing right in profile"),
    ("up", "facing away from the viewer"),
)
PHASES = (
    (
        "left-step",
        "tiny in-place left-foot walking phase; both feet remain directly beneath the torso, stride no wider than shoulder width, no kick or long lunge",
    ),
    ("idle", "neutral centered standing frame with both feet directly beneath the torso"),
    (
        "right-step",
        "tiny in-place right-foot walking phase; both feet remain directly beneath the torso, stride no wider than shoulder width, no kick or long lunge",
    ),
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


def identity_prompt() -> str:
    return (
        "single original adult Plushtopia character-creator base body, balanced natural adult proportions, "
        "bald head with no hair layer, neutral readable face, fitted neutral gray sleeveless base underlayer and fitted knee-length base shorts only, "
        "no loose shirt, no loose pants, no coat, no skirt, no armor, no accessories, no jewelry, no weapons, no props, "
        "arms relaxed close to the torso, feet close together beneath the hips, full body visible from head to feet, centered, one person only, "
        "clean polished 2D fantasy JRPG game art, simple pure white background, no text, no border, no turnaround sheet, no extra figures, normal anatomy"
    )


def frame_prompt(direction_text: str, phase_text: str) -> str:
    return (
        "Preserve the exact same adult base-body identity, anatomy, proportions, skin appearance, fitted sleeveless base underlayer and fitted base shorts from the reference. "
        "Do not add hair, loose clothing layers, accessories, armor, weapons, jewelry or props. "
        "Keep the torso upright, arms close to the body, feet within the compact footprint of a 48-pixel JRPG cell, and motion subtle rather than illustrative. "
        f"Render the same creator base as a compact JRPG movement sprite source, {direction_text}, {phase_text}, "
        "full body visible, centered, one person only, simple pure white background, no text, no border, no shadow puddle, normal anatomy."
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
        self.pipe = DiffusionPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
            cache_dir=CACHE_DIR,
        ).to("cuda")

    def _generate(self, prompt: str, seed: int, reference=None):
        generator = self.torch.Generator(device="cuda").manual_seed(seed)
        kwargs = dict(
            prompt=prompt,
            width=512,
            height=512,
            guidance_scale=1.0,
            num_inference_steps=4,
            generator=generator,
        )
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
                out = io.BytesIO()
                frame.save(out, format="PNG")
                cells.append(base64.b64encode(out.getvalue()).decode("ascii"))
                frames.append({"index": index, "direction": direction, "phase": phase, "seed": seed})
                timings.append(elapsed)
                index += 1
        ref = io.BytesIO()
        reference.save(ref, format="PNG")
        return {
            "model": MODEL_ID,
            "reference_png": base64.b64encode(ref.getvalue()).decode("ascii"),
            "reference_seconds": ref_seconds,
            "reference_seed": REFERENCE_SEED,
            "cells": cells,
            "frames": frames,
            "timings": timings,
        }


def _extract_cells(encoded_cells: list[str]) -> tuple[list[bytes], list[dict]]:
    extractor = modal.Cls.from_name(WORKER_APP, EXTRACTOR_CLASS)()
    cleaned: list[bytes] = []
    metadata: list[dict] = []
    for index, encoded in enumerate(encoded_cells):
        result = extractor.extract.remote({"image_base64": encoded})
        raw = base64.b64decode(result["image_base64"], validate=True)
        cleaned.append(raw)
        metadata.append(
            {
                "cell_index": index,
                "provider": result.get("provider"),
                "model": result.get("model"),
                "elapsed_seconds": result.get("elapsed_seconds"),
                "sha256": result.get("sha256"),
                "bytes": result.get("bytes"),
            }
        )
    return cleaned, metadata


def _bbox_width(bbox: list[int]) -> int:
    return int(bbox[2]) - int(bbox[0])


def _bbox_height(bbox: list[int]) -> int:
    return int(bbox[3]) - int(bbox[1])


def _require_compact_motion(occupied: list[list[int]]) -> dict:
    if len(occupied) != 12:
        raise RuntimeError(f"expected 12 creator cells, got {len(occupied)}")
    rows = []
    for row in range(4):
        cells = occupied[row * 3 : row * 3 + 3]
        widths = [_bbox_width(b) for b in cells]
        heights = [_bbox_height(b) for b in cells]
        idle_width = widths[1]
        width_limit = max(idle_width * 2.2, idle_width + 8)
        if widths[0] > width_limit or widths[2] > width_limit:
            raise RuntimeError(
                f"creator body row {row} stride silhouette too wide: widths={widths}, idle={idle_width}, limit={width_limit:.2f}"
            )
        if min(heights) < max(1, int(max(heights) * 0.82)):
            raise RuntimeError(f"creator body row {row} height consistency failed: {heights}")
        rows.append({"row": row, "widths": widths, "heights": heights, "width_limit": width_limit})
    return {"rows": rows, "passed": True}


@app.local_entrypoint()
def main():
    from PIL import Image
    from modal_worker.production_factory import build_single_character

    remote = CreatorBodyRunner().generate.remote()
    cleaned, extraction = _extract_cells(remote["cells"])
    package = build_single_character(cleaned, cell_width=CELL, cell_height=CELL, padding=1)
    meta = package["metadata"]
    if (meta["width"], meta["height"]) != (144, 192):
        raise RuntimeError(f"creator body geometry mismatch: {meta['width']}x{meta['height']}")
    if meta["profile"] != "mv_single_character" or not meta["engine_validation"]["valid"] or not meta["has_alpha"]:
        raise RuntimeError(f"creator body engine validation failed: {meta}")

    Path(OUTPUT_PNG).write_bytes(package["png"])
    Path(REFERENCE_PNG).write_bytes(base64.b64decode(remote["reference_png"], validate=True))

    with Image.open(OUTPUT_PNG) as sheet:
        rgba = sheet.convert("RGBA")
        occupied = []
        for row in range(4):
            for col in range(3):
                cell = rgba.crop((col * 48, row * 48, (col + 1) * 48, (row + 1) * 48)).getchannel("A")
                bbox = cell.getbbox()
                if bbox is None:
                    raise RuntimeError(f"creator body cell {row},{col} is empty")
                occupied.append(list(bbox))

    motion_gate = _require_compact_motion(occupied)
    report = {
        "schema": "plushbound.creator_body_canary.v2",
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
        "extraction": extraction,
        "extraction_backend": "deployed_birefnet",
        "sheet": meta,
        "cell_alpha_bboxes": occupied,
        "compact_motion_gate": motion_gate,
        "output_png": OUTPUT_PNG,
        "reference_png": REFERENCE_PNG,
        "catalog_wide_launch_authorized": False,
    }
    Path(REPORT_JSON).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"frame_manifest", "generation_seconds", "extraction", "cell_alpha_bboxes", "sheet", "compact_motion_gate"}
            },
            sort_keys=True,
        )
    )
