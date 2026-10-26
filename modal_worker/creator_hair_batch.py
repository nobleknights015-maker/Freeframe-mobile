"""Bounded production runner for paired creator hair assets.

One hairstyle spends five diffusion renders (one reference + four directions) and
four BiRefNet extractions. The cleaned source sheet is deterministically split into
matching front/back creator layers. This file is intentionally separate from the
live archetype canary runner so queued canary jobs cannot change underneath us.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path

import modal

from modal_worker.creator_hair_style_catalog import get_style
from modal_worker.creator_hair_splitter import CELL, DIRECTIONS, SHEET_H, SHEET_W, split_sheet, style_envelope

APP_NAME = "freeframe-creator-hair-batch"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUT_ROOT = "creator-hair-batch-output"

DIRECTION_TEXT = {
    "down": "front-facing view toward the viewer",
    "left": "left profile view",
    "right": "right profile view",
    "up": "rear-facing view showing the complete rear hairstyle structure",
}

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install("accelerate", "diffusers", "numpy", "pillow>=10.4,<12", "safetensors", "sentencepiece", "torch>=2.6,<3", "transformers")
    .add_local_python_source("modal_worker")
)
app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


def _style_prompt(style: dict) -> str:
    return (
        "isolated original fantasy JRPG complete hairstyle only, "
        f"{style['front_description']}, {style['back_description']}, "
        "cool graphite-silver neutral hair color suitable for deterministic tinting, clean readable grouped locks, "
        "polished Plushtopia anime-JRPG rendering, full crown and complete rear length/shape visible where the style has one, "
        "floating hairstyle with no head, no scalp skin, no face, no eyes, no ears, no neck, no body, no mannequin, "
        "no clothing, no accessories, one hairstyle object only, centered on pure white background, no text, no border"
    )


def _direction_prompt(style: dict, direction: str) -> str:
    return (
        "Preserve the exact same hairstyle identity, lock grouping, length, silhouette, and graphite-silver neutral color from the reference. "
        f"Render only the isolated complete hairstyle as a {DIRECTION_TEXT[direction]}. "
        f"The intended hairstyle is {style['front_description']}; rear structure is {style['back_description']}. "
        "Hair only: no scalp skin, no head, no face, no eyes, no ears, no neck, no body, no mannequin, no clothing, no accessories. "
        "Keep the full hairstyle structure readable but compact enough for a 48px RPG character cell, centered on pure white background, "
        "one object only, no text, no border."
    )


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=120, timeout=1200)
class CreatorHairBatchRunner:
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
    def generate(self, style_index: int) -> dict:
        if not 1 <= style_index <= 96:
            raise ValueError("style_index must be 1..96")
        style = get_style(style_index)
        ref_seed = 830000 + style_index * 100
        reference, ref_seconds = self._generate(_style_prompt(style), ref_seed)
        ref_buf = io.BytesIO(); reference.save(ref_buf, format="PNG")
        outputs = []
        for offset, direction in enumerate(DIRECTIONS, start=1):
            seed = ref_seed + offset
            frame, elapsed = self._generate(_direction_prompt(style, direction), seed, reference)
            buf = io.BytesIO(); frame.save(buf, format="PNG")
            outputs.append({"direction": direction, "seed": seed, "seconds": elapsed, "png": base64.b64encode(buf.getvalue()).decode("ascii")})
        return {
            "style": style,
            "model": MODEL_ID,
            "reference_seed": ref_seed,
            "reference_seconds": ref_seconds,
            "reference_png": base64.b64encode(ref_buf.getvalue()).decode("ascii"),
            "directions": outputs,
        }


def _extract(encoded: str) -> bytes:
    extractor = modal.Cls.from_name("freeframe-worker", "FreeFrameExtractor")()
    result = extractor.extract.remote({"image_base64": encoded})
    return base64.b64decode(result["image_base64"], validate=True)


def _piece(payload: bytes, max_w: int, max_h: int):
    from PIL import Image
    with Image.open(io.BytesIO(payload)) as source:
        rgba = source.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        if bbox is None:
            raise RuntimeError("hair extraction is empty")
        piece = rgba.crop(bbox)
        scale = min(max_w / piece.width, max_h / piece.height, 1.0)
        if scale < 1.0:
            piece = piece.resize((max(1, round(piece.width * scale)), max(1, round(piece.height * scale))), Image.Resampling.LANCZOS)
        return piece, {"source_bbox": list(bbox), "normalized_size": list(piece.size)}


def _source_sheet(pieces: dict[str, object]):
    from PIL import Image
    sheet = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))
    for row, direction in enumerate(DIRECTIONS):
        piece = pieces[direction]
        for col in range(3):
            x = col * CELL + 24 - piece.width // 2
            sheet.alpha_composite(piece, dest=(x, row * CELL + 1))
    return sheet


@app.local_entrypoint()
def main(style_index: int):
    import numpy as np
    from PIL import Image

    style_index = int(style_index)
    if not 1 <= style_index <= 96:
        raise ValueError("style_index must be 1..96")
    out_dir = Path(OUT_ROOT) / f"style-{style_index:03d}"
    source_dir = out_dir / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)

    remote = CreatorHairBatchRunner().generate.remote(style_index)
    style = remote["style"]
    (out_dir / f"creator-hair-{style_index:03d}-reference.png").write_bytes(base64.b64decode(remote["reference_png"], validate=True))

    max_w, max_h = style_envelope(style_index)
    pieces = {}
    extraction = []
    for item in remote["directions"]:
        direction = item["direction"]
        cleaned = _extract(item["png"])
        piece, meta = _piece(cleaned, max_w, max_h)
        pieces[direction] = piece
        piece.save(source_dir / f"{direction}-normalized.png", format="PNG", optimize=False)
        extraction.append({"direction": direction, "seed": item["seed"], "seconds": item["seconds"], **meta})

    source_sheet = _source_sheet(pieces)
    source_path = out_dir / f"creator-hair-source-{style_index:03d}.png"
    source_sheet.save(source_path, format="PNG", optimize=False)

    front, back, split_report = split_sheet(source_sheet, style_index)
    front_path = out_dir / f"creator-front-hair-{style_index:03d}.png"
    back_path = out_dir / f"creator-back-hair-{style_index:03d}.png"
    front.save(front_path, format="PNG", optimize=False)
    back.save(back_path, format="PNG", optimize=False)

    src_a = np.array(source_sheet.getchannel("A")) > 0
    front_a = np.array(front.getchannel("A")) > 0
    back_a = np.array(back.getchannel("A")) > 0
    if (front_a & back_a).any() or not ((front_a | back_a) == src_a).all():
        raise RuntimeError("front/back alpha partition invalid")
    if not front_a.any():
        raise RuntimeError("front hair layer is empty")

    report = {
        "schema": "plushbound.creator_hair_batch.v1",
        "style_index": style_index,
        "style_name": style["style_name"],
        "front_logical_id": style["front_logical_id"],
        "back_logical_id": style["back_logical_id"],
        "status": "generated_pending_visual_review",
        "model": remote["model"],
        "paid_render_count": 5,
        "paid_extraction_count": 4,
        "reference_seed": remote["reference_seed"],
        "reference_seconds": remote["reference_seconds"],
        "extraction_backend": "deployed_birefnet",
        "extraction": extraction,
        "splitter_report": split_report,
        "alpha_validation": {"source_pixels": int(src_a.sum()), "front_pixels": int(front_a.sum()), "back_pixels": int(back_a.sum()), "disjoint": True, "lossless_union": True},
        "catalog_wide_launch_authorized": False,
        "next_gate": "visual QC before banking",
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"schema": report["schema"], "style_index": style_index, "renders": 5, "extractions": 4}, sort_keys=True))
