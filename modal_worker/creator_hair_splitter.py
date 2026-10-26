"""Deterministic paired creator-hair splitter.

One isolated hairstyle source sheet can feed both creator/front-hair and
creator/back-hair. The source remains neutral/tintable. This module rescales each
48px directional cell to a style-class envelope, then partitions pixels into a
front layer (crown/fringe/face framing) and a back layer (rear mass/length).
No diffusion decisions, canvas geometry, or layer placement happen here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

CELL = 48
SHEET_W = 144
SHEET_H = 192
ANCHOR_X = 24
ANCHOR_Y = 1
DIRECTIONS = ("down", "left", "right", "up")

# 24 base hairstyles, each with four fringe variants. Values are the maximum
# normalized source envelope per style class inside one 48x48 cell.
#
# These envelopes intentionally preserve visible torso/leg readability. Earlier
# long-style values around 38-42px tall were machine-valid but visually behaved
# like floor-length curtains at game scale. The current table is bounded to the
# compact silhouettes proven by the 021/057/065 archetype composite review.
_BASE_ENVELOPES = (
    (30, 18),  # short_swept_crop
    (28, 17),  # textured_pixie
    (32, 21),  # ear_length_bob
    (34, 23),  # chin_length_bob
    (36, 27),  # shoulder_straight
    (34, 30),  # long_straight
    (34, 22),  # soft_wave_bob
    (38, 28),  # shoulder_waves
    (38, 32),  # long_waves
    (34, 22),  # short_curls
    (38, 28),  # shoulder_curls
    (38, 32),  # long_curls
    (34, 22),  # short_coils
    (38, 28),  # medium_coils
    (36, 32),  # long_coils
    (38, 30),  # low_ponytail
    (36, 29),  # high_ponytail
    (40, 30),  # twin_low_tails
    (36, 32),  # single_braid
    (40, 32),  # twin_braids
    (40, 31),  # rope_twists
    (40, 31),  # locs_medium
    (36, 24),  # low_bun
    (38, 27),  # layered_shag
)


def style_envelope(style_index: int) -> tuple[int, int]:
    if not 1 <= style_index <= 96:
        raise ValueError("style_index must be 1..96")
    base_index = (style_index - 1) // 4
    return _BASE_ENVELOPES[base_index]


def _normalize_cell(cell: Image.Image, max_w: int, max_h: int) -> Image.Image:
    rgba = cell.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError("empty hairstyle source cell")
    piece = rgba.crop(bbox)
    scale = min(max_w / piece.width, max_h / piece.height, 1.0)
    if scale < 1.0:
        piece = piece.resize(
            (max(1, round(piece.width * scale)), max(1, round(piece.height * scale))),
            Image.Resampling.LANCZOS,
        )
    out = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    x = ANCHOR_X - piece.width // 2
    out.alpha_composite(piece, dest=(x, ANCHOR_Y))
    return out


def _split_cell(cell: Image.Image, direction: str) -> tuple[Image.Image, Image.Image, dict]:
    import numpy as np

    rgba = cell.convert("RGBA")
    data = np.array(rgba)
    alpha = data[:, :, 3] > 0
    ys, xs = np.where(alpha)
    if len(xs) == 0:
        raise RuntimeError("normalized hairstyle cell is empty")

    top, bottom = int(ys.min()), int(ys.max())
    left, right = int(xs.min()), int(xs.max())
    height = bottom - top + 1
    center_x = (left + right) / 2.0
    yy, xx = np.indices(alpha.shape)

    # Crown cap is always in front so the bald base head never punches through.
    cap_depth = max(5, min(10, round(height * 0.42)))
    cap = alpha & (yy <= top + cap_depth)
    head_limit = min(bottom, top + 21)

    if direction == "down":
        # All head-zone pixels belong to the visible front layer; only true rear
        # length below the head zone drops behind the body.
        front_mask = alpha & (yy <= head_limit)
    elif direction == "left":
        front_mask = cap | (alpha & (yy <= head_limit) & (xx <= center_x + 1))
    elif direction == "right":
        front_mask = cap | (alpha & (yy <= head_limit) & (xx >= center_x - 1))
    elif direction == "up":
        front_mask = cap
    else:
        raise ValueError(f"unknown direction: {direction}")

    back_mask = alpha & ~front_mask
    front_data = np.zeros_like(data)
    back_data = np.zeros_like(data)
    front_data[front_mask] = data[front_mask]
    back_data[back_mask] = data[back_mask]

    front = Image.fromarray(front_data, "RGBA")
    back = Image.fromarray(back_data, "RGBA")

    if (front_mask & back_mask).any():
        raise RuntimeError("front/back masks overlap")
    if not ((front_mask | back_mask) == alpha).all():
        raise RuntimeError("front/back masks do not reconstruct source alpha")

    return front, back, {
        "source_bbox": [left, top, right + 1, bottom + 1],
        "front_pixels": int(front_mask.sum()),
        "back_pixels": int(back_mask.sum()),
        "source_pixels": int(alpha.sum()),
        "cap_depth": cap_depth,
        "head_limit": head_limit,
    }


def split_sheet(source: Image.Image, style_index: int) -> tuple[Image.Image, Image.Image, dict]:
    source = source.convert("RGBA")
    if source.size != (SHEET_W, SHEET_H):
        raise ValueError(f"source must be {(SHEET_W, SHEET_H)}, got {source.size}")
    max_w, max_h = style_envelope(style_index)
    front_sheet = Image.new("RGBA", source.size, (0, 0, 0, 0))
    back_sheet = Image.new("RGBA", source.size, (0, 0, 0, 0))
    cells = []

    for row, direction in enumerate(DIRECTIONS):
        for col in range(3):
            box = (col * CELL, row * CELL, (col + 1) * CELL, (row + 1) * CELL)
            normalized = _normalize_cell(source.crop(box), max_w, max_h)
            front, back, meta = _split_cell(normalized, direction)
            front_sheet.alpha_composite(front, dest=(col * CELL, row * CELL))
            back_sheet.alpha_composite(back, dest=(col * CELL, row * CELL))
            cells.append({"direction": direction, "column": col, **meta})

    return front_sheet, back_sheet, {
        "schema": "plushbound.creator_hair_splitter.v1",
        "style_index": style_index,
        "front_logical_id": f"creator/front-hair/{style_index:03d}",
        "back_logical_id": f"creator/back-hair/{style_index:03d}",
        "source_geometry": "144x192 RGBA 3x4-48px",
        "envelope": {"max_width": max_w, "max_height": max_h},
        "layer_order": ["back_hair", "body", "front_hair"],
        "cells": cells,
        "paid_renders": 0,
        "paid_extractions": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--style-index", type=int, required=True)
    parser.add_argument("--front-out", required=True)
    parser.add_argument("--back-out", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    with Image.open(args.source) as image:
        front, back, report = split_sheet(image, args.style_index)
    front.save(args.front_out, format="PNG", optimize=False)
    back.save(args.back_out, format="PNG", optimize=False)
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"schema": report["schema"], "style_index": args.style_index}, sort_keys=True))


if __name__ == "__main__":
    main()
