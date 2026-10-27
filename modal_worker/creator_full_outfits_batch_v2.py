"""Hardened Creator Full Outfits finishing wrapper.

This wrapper preserves the original bounded Vera source-generation contract while
preventing transparent/white gaps inside extracted coordinated outfits from being
reintroduced when compiler-owned alpha is applied. Generated alpha is used only
to clean/fill texture holes; final Engine v1 geometry remains entirely locked.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageStat

from modal_worker import creator_full_outfits_batch as base

app = base.app
OUT_ROOT = base.OUT_ROOT
CELL = base.CELL
SHEET_W = base.SHEET_W
SHEET_H = base.SHEET_H
DIRECTIONS = base.DIRECTIONS


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


def _compile_sheet(style: dict, pieces: dict[str, Image.Image]) -> tuple[Image.Image, dict]:
    del style
    locked = base._locked_outfit_mask()
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
    style = base.get_style(style_index)
    out_dir = Path(OUT_ROOT) / f"style-{style_index:03d}"
    raw_dir = out_dir / "sources" / "raw"
    extracted_dir = out_dir / "sources" / "extracted"
    raw_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    print(f"creator full outfit {style_index:03d}: starting Vera render batch", flush=True)
    remote = base.CreatorFullOutfitsBatchRunner().generate.remote(style_index)
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
        piece = base._border_white_extract(item["png"])
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
    (out_dir / "catalog_snapshot.json").write_text(json.dumps(base.snapshot(), indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "schema": report["schema"],
        "style_index": style_index,
        "renders": 5,
        "paid_extractions": 0,
        "raw_sources_persisted": 5,
        "texture_fill_backend": report["texture_fill_backend"],
    }, sort_keys=True), flush=True)
