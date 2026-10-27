"""Self-contained hardened Creator Full Outfits production runner.

Vera creates one coordinated outfit reference plus four directional outfit-only
renders. Paid sources are persisted before deterministic local extraction. The
compiler owns all final Engine v1 alpha/geometry using the accepted Tops+Bottoms
motion-mask union. Extracted alpha is used only to fill source texture holes so
white background cannot be reintroduced into the locked clothing silhouette.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path

import modal
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageStat

from modal_worker.creator_full_outfits_style_catalog import get_style, snapshot

APP_NAME = "freeframe-creator-full-outfits-batch-v2"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
OUT_ROOT = "creator-full-outfits-batch-output"
CELL = 48
SHEET_W = 144
SHEET_H = 192
DIRECTIONS = ("down", "left", "right", "up")
DIRECTION_TEXT = {
    "down": "front-facing view toward the viewer",
    "left": "left profile view",
    "right": "right profile view",
    "up": "rear-facing view showing the back of the outfit",
}

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "accelerate",
        "diffusers",
        "numpy",
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


def _style_prompt(style: dict) -> str:
    return (
        "isolated original Plushtopia fantasy JRPG complete coordinated clothing outfit, upper garment plus lower garment as one cohesive ensemble, "
        f"{style['brief']}, {style['variant']} interpretation, "
        "RPG Maker MV cover-art / MV Trinity-inspired polish without copying proprietary artwork, "
        "clean anime-JRPG fabric rendering, visible stitching and handcrafted textile detail, restrained neutral base colors suitable for later tinting, "
        "upper and lower garments must meet or overlap naturally at the waist with no white gap between them, arranged exactly as if worn together, "
        "clothing only on pure white background: no person, no mannequin, no head, no face, no hair, no skin, no hands, no exposed body, "
        "no shoes, no hat, no jewelry, no weapon, no prop, no text, one centered coordinated outfit"
    )


def _direction_prompt(style: dict, direction: str) -> str:
    return (
        "Preserve the exact same complete outfit identity, construction, seams, trim, fabric, palette, upper garment and lower garment from the reference. "
        f"Render the isolated complete coordinated outfit only as a {DIRECTION_TEXT[direction]}. "
        f"Design brief: {style['brief']}; variant: {style['variant']}. "
        "Keep upper and lower garments meeting or overlapping naturally at the waist with no white gap between pieces. "
        "No person, mannequin, head, face, hair, skin, hands, exposed body, shoes, hat, jewelry, weapon or prop. "
        "Keep collar, sleeves, waist, hems, panels and leg separation readable at small JRPG sprite scale, centered on pure white background, no text, no border."
    )


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=120, timeout=1200)
class CreatorFullOutfitsBatchRunner:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import DiffusionPipeline

        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(
            MODEL_ID, torch_dtype=torch.bfloat16, cache_dir=CACHE_DIR
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
        output = self.pipe(**kwargs).images[0]
        return output, round(time.monotonic() - started, 3)

    @modal.method()
    def generate(self, style_index: int) -> dict:
        style = get_style(style_index)
        seed0 = 960000 + int(style_index) * 100
        reference, reference_seconds = self._generate(_style_prompt(style), seed0)
        reference_buffer = io.BytesIO()
        reference.save(reference_buffer, format="PNG")
        directions = []
        for offset, direction in enumerate(DIRECTIONS, start=1):
            frame, elapsed = self._generate(
                _direction_prompt(style, direction), seed0 + offset, reference
            )
            frame_buffer = io.BytesIO()
            frame.save(frame_buffer, format="PNG")
            directions.append({
                "direction": direction,
                "seed": seed0 + offset,
                "seconds": elapsed,
                "png": base64.b64encode(frame_buffer.getvalue()).decode("ascii"),
            })
        return {
            "style": style,
            "model": MODEL_ID,
            "reference_seed": seed0,
            "reference_seconds": reference_seconds,
            "reference_png": base64.b64encode(reference_buffer.getvalue()).decode("ascii"),
            "directions": directions,
        }


def _border_white_extract(encoded: str) -> Image.Image:
    raw = base64.b64decode(encoded, validate=True)
    with Image.open(io.BytesIO(raw)) as source:
        rgb = source.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    seen = bytearray(width * height)
    stack: list[tuple[int, int]] = []

    def candidate(x: int, y: int) -> bool:
        r, g, b = pixels[x, y]
        return r >= 210 and g >= 210 and b >= 210

    def push(x: int, y: int) -> None:
        index = y * width + x
        if not seen[index] and candidate(x, y):
            seen[index] = 1
            stack.append((x, y))

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(height):
        push(0, y)
        push(width - 1, y)
    while stack:
        x, y = stack.pop()
        if x:
            push(x - 1, y)
        if x + 1 < width:
            push(x + 1, y)
        if y:
            push(x, y - 1)
        if y + 1 < height:
            push(x, y + 1)

    alpha = bytearray(b"\xff") * (width * height)
    for index, is_background in enumerate(seen):
        if is_background:
            alpha[index] = 0
    rgba = rgb.convert("RGBA")
    rgba.putalpha(Image.frombytes("L", (width, height), bytes(alpha)))
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError("deterministic full-outfit extraction is empty")
    return rgba.crop(bbox)


def _opaque_texture(piece: Image.Image) -> Image.Image:
    rgba = piece.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getbbox() is None:
        raise RuntimeError("full-outfit texture source is empty")
    rgb = rgba.convert("RGB")
    stats = ImageStat.Stat(rgb, mask=alpha)
    fill = tuple(max(0, min(255, int(round(value)))) for value in stats.mean)
    opaque = Image.new("RGB", rgba.size, fill)
    opaque.paste(rgb, (0, 0), alpha)
    return opaque.convert("RGBA")


def _locked_outfit_mask() -> Image.Image:
    from modal_worker.creator_tops_batch import _locked_mask as locked_top_mask
    from modal_worker.creator_bottoms_batch import _locked_mask as locked_bottom_mask

    top = locked_top_mask()
    bottom = locked_bottom_mask()
    if top.size != (SHEET_W, SHEET_H) or bottom.size != (SHEET_W, SHEET_H):
        raise RuntimeError("locked clothing masks have incompatible dimensions")
    return ImageChops.lighter(top, bottom)


def _compile_sheet(style: dict, pieces: dict[str, Image.Image]) -> tuple[Image.Image, dict]:
    del style
    locked = _locked_outfit_mask()
    output = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))
    stats = []
    for row, direction in enumerate(DIRECTIONS):
        texture_source = _opaque_texture(pieces[direction])
        for col in range(3):
            box = (col * CELL, row * CELL, (col + 1) * CELL, (row + 1) * CELL)
            cell_mask = locked.crop(box)
            bbox = cell_mask.getbbox()
            if bbox is None:
                raise RuntimeError(f"empty full-outfit mask row={row} col={col}")
            x0, y0, x1, y1 = bbox
            if y0 < 4 or y1 > 46:
                raise RuntimeError("full-outfit mask escaped accepted clothing safe window")
            texture = texture_source.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
            patch = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
            patch.paste(texture, (x0, y0))
            patch.putalpha(cell_mask)
            eroded = cell_mask.filter(ImageFilter.MinFilter(3))
            edge = ImageChops.subtract(cell_mask, eroded)
            dark = ImageEnhance.Brightness(patch).enhance(0.66)
            patch = Image.composite(dark, patch, edge)
            output.alpha_composite(patch, dest=(col * CELL, row * CELL))
            stats.append({"direction": direction, "phase": col, "bbox": [x0, y0, x1, y1]})
    return output, {
        "locked_motion_mask": True,
        "mask_contract": "creator_tops_union_creator_bottoms_v1",
        "texture_fill_backend": "opaque_mean_fabric_v1",
        "cells": stats,
    }


@app.local_entrypoint()
def main(style_index: int):
    style_index = int(style_index)
    style = get_style(style_index)
    out_dir = Path(OUT_ROOT) / f"style-{style_index:03d}"
    raw_dir = out_dir / "sources" / "raw"
    extracted_dir = out_dir / "sources" / "extracted"
    raw_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    print(f"creator full outfit {style_index:03d}: starting Vera render batch", flush=True)
    remote = CreatorFullOutfitsBatchRunner().generate.remote(style_index)
    print(f"creator full outfit {style_index:03d}: Vera render batch complete; persisting paid sources", flush=True)

    reference_raw = base64.b64decode(remote["reference_png"], validate=True)
    (out_dir / f"creator-full-outfit-{style_index:03d}-reference.png").write_bytes(reference_raw)
    (raw_dir / "reference.png").write_bytes(reference_raw)
    for item in remote["directions"]:
        (raw_dir / f"{item['direction']}.png").write_bytes(base64.b64decode(item["png"], validate=True))
    print(f"creator full outfit {style_index:03d}: all five paid renders safely persisted", flush=True)

    pieces: dict[str, Image.Image] = {}
    extraction = []
    for item in remote["directions"]:
        direction = item["direction"]
        piece = _border_white_extract(item["png"])
        pieces[direction] = piece
        piece.save(extracted_dir / f"{direction}.png", format="PNG", optimize=False)
        extraction.append({
            "direction": direction,
            "seed": item["seed"],
            "seconds": item["seconds"],
            "extracted_size": list(piece.size),
        })

    sheet, geometry = _compile_sheet(style, pieces)
    output_path = out_dir / f"creator-full-outfit-{style_index:03d}.png"
    sheet.save(output_path, format="PNG", optimize=False)
    if sheet.getchannel("A").getbbox() is None:
        raise RuntimeError("compiled full-outfit sheet is empty")

    report = {
        "schema": "plushbound.creator_full_outfits_batch.v1",
        "style_index": style_index,
        "logical_id": style["logical_id"],
        "style": style,
        "status": "generated_pending_visual_review",
        "model": remote["model"],
        "paid_render_count": 5,
        "paid_extraction_count": 0,
        "reference_seed": remote["reference_seed"],
        "reference_seconds": remote["reference_seconds"],
        "extraction_backend": "deterministic_border_connected_white_v1",
        "texture_fill_backend": "opaque_mean_fabric_v1",
        "source_art_persisted_before_extraction": True,
        "generated_alpha_used_for_texture_cleanup_only": True,
        "extraction": extraction,
        "dimensions": [SHEET_W, SHEET_H],
        "layout": "3x4-48px",
        "geometry": geometry,
        "compiler_owns_final_geometry": True,
        "generated_alpha_discarded_for_final_geometry": True,
        "catalog_wide_launch_authorized": False,
        "clothing_strategy": "full_outfits_primary_modular_tops_optional_bottoms_deferred",
        "next_gate": "locked-body visual QC before banking",
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out_dir / "catalog_snapshot.json").write_text(json.dumps(snapshot(), indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "schema": report["schema"],
        "style_index": style_index,
        "renders": 5,
        "paid_extractions": 0,
        "raw_sources_persisted": 5,
        "texture_fill_backend": report["texture_fill_backend"],
    }, sort_keys=True), flush=True)
