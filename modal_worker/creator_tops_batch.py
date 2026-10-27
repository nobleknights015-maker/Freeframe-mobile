"""Bounded source-art + deterministic compiler for reduced-V1 Creator Tops.

Vera/FLUX creates one reference plus four directional garment-only renders per
style. BiRefNet extracts garment pixels. Final 144x192 Engine v1 animation
geometry is compiler-owned: extracted directional art is texture-mapped onto a
locked upper-garment motion mask derived from accepted Creator Body geometry.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path

import modal
from PIL import Image, ImageChops, ImageEnhance, ImageFilter

from modal_worker.creator_tops_style_catalog import get_style, snapshot

APP_NAME = "freeframe-creator-tops-batch"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUT_ROOT = "creator-tops-batch-output"
CELL = 48
SHEET_W = 144
SHEET_H = 192
DIRECTIONS = ("down", "left", "right", "up")
DIRECTION_TEXT = {
    "down": "front-facing view toward the viewer",
    "left": "left profile view",
    "right": "right profile view",
    "up": "rear-facing view showing the back of the garment",
}

# 144x192 locked upper-garment motion mask. It preserves the accepted broad-body
# walk geometry and therefore carries sleeve/torso movement across all 12 cells.
MASK_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAJAAAADACAAAAADOo7WTAAADFUlEQVR4nO2c25LjIAxEYWr//5eZh9wWkGgJZMyk+jykKonAbczFSEBKhJBryd0v5fVzkf8X7HOdENo/rGT7f8OEmPL4yC/7AiQ9rbKa/4/psjZdIdT3I+U7umNZh57CYI9LqMTdvYVKkHJpVZFXqiX/oDpkua6NKwQtcZygpkWENLOLW9kQ4dp5cAPiX3ls0tyEbShw2KP8uxLCCtZA+R9XqSkI0QkKGg6m7c8vobtBgrY/wT9XQtuhIMQFrx+WeZBuv7uEYCs87pERQgghhBBCvox2ElXmvYzOpEp4TYiXlXc8zpb/w/ATOFtDdgvn54TOlH1JKX/mf1ZFrxStPfJTxzuqgaca+qnh3HfVRdV83+70RETP7b2hhY5WUG8/ziGggOosjvN+UBBCX9mQvIPIRCctJKFLD9EKGkVMt9DWoZV+5b0Qx5UEjWV3EyjIVLhwNc7mEir9KxwY7fN0rY7phtpKvfZKHcHokbmkPY2BrJzR2+5w6PAwUUBikkZQtXouYA5hEzEQ1CXfvhQksqcOYXdPffdQSQghhBBCCNkNXKRocc1PeqnElP1E0RGYmtIEAmvKDrz0jpmhK71nlkZJyB7Ey5yxFIOoKsHlfmo8ES+DbyklGA3av2Ugegm8N7vwJfDuiCjim/3UMXyfoJymIjZqCsXHmK21070/7mWXlQvA8JSv2RTjNl3dqusYZ9ptZGcVVKndlUgd7hVBznuecuPLioJCC/7lOo4FTc0Vxpibo5y4Ry0hrVk2TDb7/9M7t+IYL5Hn9KTUNmxQh5aDzGNz/xujuVsK64rW16D5ahF8B4d16NJ4lTDSfN/rR13sty8dIYQQQgghhJyGHA0anJco2n8SOOzl/OV1jO7ZYVxM5LiJIj6PcfHkN0OCyJPi4qnUaU9Wu+Ur7I8rIQpCVIKsketZe0s2ayVkOF+x+mfiPEZ0olOH1yeJXJL6ygZb/uH2Z1fqE/g+QVdvTd58tDFPG/QTvYtz+Yl38bJ2ARFYNefV//c33t7O4mHH/vMY0fANl3zt3nB23CMjhBBCCNnML5rvu8d55DqTAAAAAElFTkSuQmCC"

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
        "isolated original Plushtopia fantasy JRPG upper-body garment only, "
        f"{style['brief']}, {style['variant']} interpretation, "
        "RPG Maker MV cover-art / MV Trinity-inspired polish without copying proprietary artwork, "
        "clean anime-JRPG fabric rendering, visible stitching and handcrafted textile detail, restrained neutral base colors suitable for later tinting, "
        "garment only on pure white background: no person, no mannequin, no head, no face, no skin, no hands, no legs, no pants, no shoes, no accessories, no text, one centered object"
    )


def _direction_prompt(style: dict, direction: str) -> str:
    return (
        "Preserve the exact same garment identity, construction, seams, trim, fabric, and color from the reference. "
        f"Render the isolated upper-body garment only as a {DIRECTION_TEXT[direction]}. "
        f"Design brief: {style['brief']}; variant: {style['variant']}. "
        "No person, no mannequin, no head, no face, no skin, no hands, no legs, no pants, no shoes, no accessories. "
        "Keep sleeves, collar, hem and fastening readable at small JRPG sprite scale, centered on pure white background, no text, no border."
    )


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=120, timeout=1200)
class CreatorTopsBatchRunner:
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
        style = get_style(style_index)
        seed0 = 940000 + int(style_index) * 100
        reference, ref_seconds = self._generate(_style_prompt(style), seed0)
        rb = io.BytesIO(); reference.save(rb, format="PNG")
        directions = []
        for offset, direction in enumerate(DIRECTIONS, start=1):
            frame, elapsed = self._generate(_direction_prompt(style, direction), seed0 + offset, reference)
            fb = io.BytesIO(); frame.save(fb, format="PNG")
            directions.append({"direction": direction, "seed": seed0 + offset, "seconds": elapsed, "png": base64.b64encode(fb.getvalue()).decode("ascii")})
        return {
            "style": style,
            "model": MODEL_ID,
            "reference_seed": seed0,
            "reference_seconds": ref_seconds,
            "reference_png": base64.b64encode(rb.getvalue()).decode("ascii"),
            "directions": directions,
        }


def _extract(encoded: str) -> Image.Image:
    extractor = modal.Cls.from_name("freeframe-worker", "FreeFrameExtractor")()
    result = extractor.extract.remote({"image_base64": encoded})
    raw = base64.b64decode(result["image_base64"], validate=True)
    with Image.open(io.BytesIO(raw)) as im:
        rgba = im.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        if bbox is None:
            raise RuntimeError("top extraction is empty")
        return rgba.crop(bbox)


def _locked_mask() -> Image.Image:
    with Image.open(io.BytesIO(base64.b64decode(MASK_PNG_B64))) as im:
        mask = im.convert("L")
    if mask.size != (SHEET_W, SHEET_H):
        raise RuntimeError("locked top mask has wrong dimensions")
    return mask


def _style_mask(base: Image.Image, style: dict) -> Image.Image:
    # Geometry remains deterministic. These tiny operations diversify silhouette
    # while preserving the locked movement pose and upper-body safe window.
    family = style["design_family"]
    variant = style["variant"]
    m = base.copy()
    if family in {"cute_plush", "regional_festival", "rugged_frontier"} or variant == "soft":
        m = m.filter(ImageFilter.MaxFilter(3))
    elif family in {"victorian_tailored", "scholar_court"} or variant == "structured":
        m = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    return m


def _fit_texture(piece: Image.Image, size: tuple[int, int]) -> Image.Image:
    if size[0] <= 0 or size[1] <= 0:
        raise RuntimeError("invalid garment mask bbox")
    return piece.resize(size, Image.Resampling.LANCZOS)


def _compile_sheet(style: dict, pieces: dict[str, Image.Image]) -> tuple[Image.Image, dict]:
    base = _style_mask(_locked_mask(), style)
    out = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))
    mask_stats = []
    for row, direction in enumerate(DIRECTIONS):
        piece = pieces[direction]
        for col in range(3):
            box = (col * CELL, row * CELL, (col + 1) * CELL, (row + 1) * CELL)
            cell_mask = base.crop(box)
            bbox = cell_mask.getbbox()
            if bbox is None:
                raise RuntimeError(f"empty top mask at row={row} col={col}")
            x0, y0, x1, y1 = bbox
            if y0 < 4 or y1 > 35:
                raise RuntimeError("top mask escaped upper-body safe window")
            texture = _fit_texture(piece, (x1 - x0, y1 - y0))
            # Compiler owns alpha. Generated skin/background cannot leak through.
            patch = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
            patch.paste(texture, (x0, y0))
            patch.putalpha(cell_mask)
            # Add a subtle deterministic darker edge for sprite-scale readability.
            eroded = cell_mask.filter(ImageFilter.MinFilter(3))
            edge = ImageChops.subtract(cell_mask, eroded)
            dark = ImageEnhance.Brightness(patch).enhance(0.66)
            patch = Image.composite(dark, patch, edge)
            out.alpha_composite(patch, dest=(col * CELL, row * CELL))
            mask_stats.append({"direction": direction, "phase": col, "bbox": [x0, y0, x1, y1], "pixels": sum(1 for v in cell_mask.getdata() if v)})
    return out, {"locked_motion_mask": True, "cells": mask_stats}


@app.local_entrypoint()
def main(style_index: int):
    style_index = int(style_index)
    style = get_style(style_index)
    out_dir = Path(OUT_ROOT) / f"style-{style_index:03d}"
    src_dir = out_dir / "sources"
    src_dir.mkdir(parents=True, exist_ok=True)

    remote = CreatorTopsBatchRunner().generate.remote(style_index)
    (out_dir / f"creator-top-{style_index:03d}-reference.png").write_bytes(base64.b64decode(remote["reference_png"], validate=True))
    pieces = {}
    extraction = []
    for item in remote["directions"]:
        piece = _extract(item["png"])
        pieces[item["direction"]] = piece
        piece.save(src_dir / f"{item['direction']}-extracted.png", format="PNG", optimize=False)
        extraction.append({"direction": item["direction"], "seed": item["seed"], "seconds": item["seconds"], "extracted_size": list(piece.size)})

    sheet, geometry = _compile_sheet(style, pieces)
    path = out_dir / f"creator-top-{style_index:03d}.png"
    sheet.save(path, format="PNG", optimize=False)
    alpha = sheet.getchannel("A")
    if alpha.getbbox() is None:
        raise RuntimeError("compiled top sheet is empty")

    report = {
        "schema": "plushbound.creator_tops_batch.v1",
        "style_index": style_index,
        "logical_id": style["logical_id"],
        "style": style,
        "status": "generated_pending_visual_review",
        "model": remote["model"],
        "paid_render_count": 5,
        "paid_extraction_count": 4,
        "reference_seed": remote["reference_seed"],
        "reference_seconds": remote["reference_seconds"],
        "extraction_backend": "deployed_birefnet",
        "extraction": extraction,
        "dimensions": [SHEET_W, SHEET_H],
        "layout": "3x4-48px",
        "geometry": geometry,
        "compiler_owns_final_geometry": True,
        "generated_alpha_discarded": True,
        "catalog_wide_launch_authorized": False,
        "next_gate": "locked-body visual QC before banking",
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out_dir / "catalog_snapshot.json").write_text(json.dumps(snapshot(), indent=2, sort_keys=True) + "\n")
    print(json.dumps({"schema": report["schema"], "style_index": style_index, "renders": 5, "extractions": 4}, sort_keys=True))
