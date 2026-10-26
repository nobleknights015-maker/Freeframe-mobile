"""Bounded production batch for the 24 proven creator/body sheets.

This promotes only the creator-body subfamily after the visual canary. Each logical
asset is an exact 144x192 RGBA 3x4-48px sheet built from one identity reference
plus twelve reference-conditioned movement frames. Other creator slots remain
locked until they receive their own production contract.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path

import modal

APP_NAME = "freeframe-creator-body-batch"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUT_ROOT = "creator-body-batch-output"
CELL = 48
BODY_COUNT = 24
BODIES_PER_LANE = 2
LANE_COUNT = 12

DIRECTIONS = (
    ("down", "facing toward the viewer"),
    ("left", "facing left in profile"),
    ("right", "facing right in profile"),
    ("up", "facing away from the viewer"),
)
PHASES = (
    ("left-step", "tiny in-place left-foot step, feet remain close to the body centerline"),
    ("idle", "neutral centered standing frame"),
    ("right-step", "tiny in-place right-foot step, feet remain close to the body centerline"),
)

# Twenty-four deliberately distinct adult body-build targets. Skin color is not
# encoded here because the catalog has a separate skin-layer family.
BODY_VARIANTS = (
    "compact petite adult build",
    "short slim adult build",
    "short balanced adult build",
    "short sturdy adult build",
    "small athletic adult build",
    "lean narrow-shouldered adult build",
    "slim balanced adult build",
    "balanced neutral adult build",
    "balanced athletic adult build",
    "balanced sturdy adult build",
    "broad-shouldered adult build",
    "stocky adult build",
    "soft rounded adult build",
    "curvy adult build",
    "strong athletic adult build",
    "muscular adult build",
    "tall slim adult build",
    "tall lean adult build",
    "tall balanced adult build",
    "tall athletic adult build",
    "tall broad adult build",
    "heavy sturdy adult build",
    "long-limbed adult build",
    "compact powerful adult build",
)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install("accelerate", "diffusers", "pillow>=10.4,<12", "safetensors", "sentencepiece", "torch>=2.6,<3", "transformers")
    .add_local_python_source("modal_worker")
)
app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


def _identity_prompt(body_desc: str) -> str:
    return (
        f"single original adult Plushtopia character-creator base body, {body_desc}, natural adult proportions, "
        "bald head with no hair layer, neutral readable face, modest close-fitting neutral gray base underlayer only, "
        "no coat, no shirt layer, no pants layer beyond the neutral base underlayer, no skirt, no armor, no accessories, "
        "no jewelry, no weapons, full body visible from head to feet, centered, one person only, clean polished 2D fantasy JRPG game art, "
        "simple pure white background, no text, no border, no turnaround sheet, no extra figures, normal anatomy"
    )


def _frame_prompt(body_desc: str, direction_text: str, phase_text: str) -> str:
    return (
        f"Preserve the exact same {body_desc}, identity, anatomy, proportions and neutral gray base underlayer from the reference. "
        "Do not add hair, clothing layers, accessories, armor, weapons, jewelry or props. Keep both feet and all limbs close to the torso footprint; "
        "this is a tiny in-place RPG walk cycle, not a stride, kick, lunge or running pose. "
        f"Render the same creator base as a compact JRPG movement sprite source, {direction_text}, {phase_text}, full body visible, centered, "
        "one person only, simple pure white background, no text, no border, normal anatomy."
    )


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=120, timeout=1800)
class CreatorBodyBatchRunner:
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
    def generate_body(self, body_index: int) -> dict:
        if not 1 <= body_index <= BODY_COUNT:
            raise ValueError("body_index must be 1..24")
        desc = BODY_VARIANTS[body_index - 1]
        reference_seed = 700000 + body_index * 100
        base_seed = reference_seed + 1
        reference, reference_seconds = self._generate(_identity_prompt(desc), reference_seed)
        cells, frames, timings = [], [], []
        idx = 0
        for direction, direction_text in DIRECTIONS:
            for phase, phase_text in PHASES:
                seed = base_seed + idx
                frame, elapsed = self._generate(_frame_prompt(desc, direction_text, phase_text), seed, reference)
                out = io.BytesIO(); frame.save(out, format="PNG")
                cells.append(base64.b64encode(out.getvalue()).decode("ascii"))
                frames.append({"index": idx, "direction": direction, "phase": phase, "seed": seed})
                timings.append(elapsed)
                idx += 1
        ref_out = io.BytesIO(); reference.save(ref_out, format="PNG")
        return {
            "body_index": body_index,
            "body_description": desc,
            "model": MODEL_ID,
            "reference_seed": reference_seed,
            "reference_seconds": reference_seconds,
            "reference_png": base64.b64encode(ref_out.getvalue()).decode("ascii"),
            "cells": cells,
            "frames": frames,
            "timings": timings,
        }


def _extract(encoded: str) -> bytes:
    extractor = modal.Cls.from_name("freeframe-worker", "FreeFrameExtractor")()
    result = extractor.extract.remote({"image_base64": encoded})
    return base64.b64decode(result["image_base64"], validate=True)


def _validate_motion(output_png: str) -> dict:
    from PIL import Image
    with Image.open(output_png) as sheet:
        rgba = sheet.convert("RGBA")
        rows = []
        for row in range(4):
            bboxes = []
            widths = []
            heights = []
            for col in range(3):
                alpha = rgba.crop((col*48, row*48, (col+1)*48, (row+1)*48)).getchannel("A")
                bbox = alpha.getbbox()
                if bbox is None:
                    raise RuntimeError(f"empty creator body cell row={row} col={col}")
                w = bbox[2]-bbox[0]; h = bbox[3]-bbox[1]
                bboxes.append(list(bbox)); widths.append(w); heights.append(h)
            idle = widths[1]
            limit = max(24.0, idle * 2.2)
            if max(widths) > limit:
                raise RuntimeError(f"creator body row {row} stride too wide: widths={widths}, limit={limit}")
            if min(heights) < 36:
                raise RuntimeError(f"creator body row {row} subject too short: heights={heights}")
            rows.append({"row":row,"bboxes":bboxes,"widths":widths,"heights":heights,"width_limit":limit})
        return {"passed": True, "rows": rows}


def _run_body(body_index: int, out_dir: Path) -> dict:
    from modal_worker.production_factory import build_single_character
    remote = CreatorBodyBatchRunner().generate_body.remote(body_index)
    cleaned = [_extract(value) for value in remote["cells"]]
    package = build_single_character(cleaned, cell_width=CELL, cell_height=CELL, padding=1)
    meta = package["metadata"]
    if (meta["width"], meta["height"]) != (144, 192):
        raise RuntimeError(f"body {body_index:03d} geometry mismatch")
    if meta["profile"] != "mv_single_character" or not meta["engine_validation"]["valid"] or not meta["has_alpha"]:
        raise RuntimeError(f"body {body_index:03d} engine validation failed")
    output = out_dir / f"creator-body-{body_index:03d}.png"
    output.write_bytes(package["png"])
    ref = out_dir / f"creator-body-{body_index:03d}-reference.png"
    ref.write_bytes(base64.b64decode(remote["reference_png"], validate=True))
    motion = _validate_motion(str(output))
    return {
        "logical_id": f"creator/body/{body_index:03d}",
        "body_index": body_index,
        "body_description": remote["body_description"],
        "status": "generated_pending_visual_review",
        "output_png": str(output),
        "reference_png": str(ref),
        "reference_seed": remote["reference_seed"],
        "reference_seconds": remote["reference_seconds"],
        "generation_seconds": remote["timings"],
        "frame_manifest": remote["frames"],
        "sheet": meta,
        "compact_motion_gate": motion,
    }


@app.local_entrypoint()
def main(lane: int):
    lane = int(lane)
    if not 0 <= lane < LANE_COUNT:
        raise ValueError("lane must be 0..11")
    start = lane * BODIES_PER_LANE + 1
    indices = list(range(start, start + BODIES_PER_LANE))
    out_dir = Path(OUT_ROOT) / f"lane-{lane:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for body_index in indices:
        results.append(_run_body(body_index, out_dir))
        (out_dir / "checkpoint.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    report = {
        "schema": "plushbound.creator_body_batch.v1",
        "lane": lane,
        "requested": len(indices),
        "completed": len(results),
        "logical_ids": [r["logical_id"] for r in results],
        "catalog_wide_launch_authorized": False,
        "results": results,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"schema":report["schema"],"lane":lane,"requested":len(indices),"completed":len(results)}, sort_keys=True))
