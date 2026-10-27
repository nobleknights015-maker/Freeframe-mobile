"""Deterministic Plushbound Creator Eyes compiler.

Compiles one stable creator/eyes logical ID into a 144x192 RGBA overlay using
Engine v1's 3x4 48px cell contract. The back/up-facing row is intentionally
transparent. This lane spends zero model renders and zero background
extractions, so all retries are deterministic and free.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

from PIL import Image

from creator_eyes_style_catalog import get_style, snapshot

CELL = 48
WIDTH = 144
HEIGHT = 192
OUTLINE = (55, 43, 48, 255)
SCLERA = (238, 231, 220, 255)
HIGHLIGHT = (250, 247, 238, 255)


def _rgba(hex_color: str) -> tuple[int, int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def _front_motif(shape: str, iris: tuple[int, int, int, int]) -> list[tuple[int, int, tuple[int, int, int, int]]]:
    # Locked common face anchor for the Engine v1 creator body family.
    left, right, y = 21, 26, 5
    px: list[tuple[int, int, tuple[int, int, int, int]]] = []

    def pair(dx: int, dy: int, color):
        px.extend(((left + dx, y + dy, color), (right - dx, y + dy, color)))

    if shape == "soft_almond":
        pair(0, 0, iris); pair(-1, 0, OUTLINE); pair(0, -1, OUTLINE); pair(0, 1, OUTLINE)
    elif shape == "round":
        pair(0, 0, iris); pair(-1, 0, SCLERA); pair(0, -1, OUTLINE); pair(0, 1, OUTLINE)
    elif shape == "wide":
        pair(0, 0, iris); pair(-1, 0, SCLERA); pair(1, 0, SCLERA); pair(0, -1, OUTLINE)
    elif shape == "narrow_almond":
        pair(0, 0, iris); pair(-1, 0, OUTLINE); pair(1, 0, OUTLINE)
    elif shape == "upturned":
        pair(0, 0, iris); pair(-1, -1, OUTLINE); pair(0, -1, OUTLINE); pair(1, 0, OUTLINE)
    elif shape == "downturned_soft":
        pair(0, 0, iris); pair(-1, 0, OUTLINE); pair(0, -1, OUTLINE); pair(1, 1, OUTLINE)
    elif shape == "heroic":
        pair(0, 0, iris); pair(-1, -1, OUTLINE); pair(0, -1, OUTLINE); pair(1, -1, OUTLINE); pair(1, 0, OUTLINE)
    elif shape == "doll":
        pair(0, 0, iris); pair(-1, 0, SCLERA); pair(0, -1, HIGHLIGHT); pair(0, 1, OUTLINE)
    else:
        raise ValueError(f"unsupported eye shape: {shape}")
    return px


def _profile_motif(facing: str, shape: str, iris: tuple[int, int, int, int]) -> list[tuple[int, int, tuple[int, int, int, int]]]:
    if facing == "left":
        cx, outward = 21, -1
    elif facing == "right":
        cx, outward = 26, 1
    else:
        raise ValueError(facing)
    y = 5
    px = [(cx, y, iris), (cx, y - 1, OUTLINE)]
    if shape in {"round", "wide", "doll"}:
        px.append((cx + outward, y, SCLERA))
    elif shape in {"heroic", "upturned"}:
        px.append((cx + outward, y - 1, OUTLINE))
    else:
        px.append((cx + outward, y, OUTLINE))
    if shape in {"soft_almond", "round", "downturned_soft", "doll"}:
        px.append((cx, y + 1, OUTLINE))
    return px


def _stamp(sheet: Image.Image, col: int, row: int, motif: Iterable[tuple[int, int, tuple[int, int, int, int]]]) -> None:
    pix = sheet.load()
    ox, oy = col * CELL, row * CELL
    for x, y, color in motif:
        if not (0 <= x < CELL and 0 <= y < CELL):
            raise RuntimeError("motif escaped 48px cell")
        pix[ox + x, oy + y] = color


def compile_style(style_index: int) -> tuple[Image.Image, dict]:
    style = get_style(style_index)
    iris = _rgba(style["iris_hex"])
    sheet = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    for col in range(3):
        _stamp(sheet, col, 0, _front_motif(style["shape_name"], iris))
        _stamp(sheet, col, 1, _profile_motif("left", style["shape_name"], iris))
        _stamp(sheet, col, 2, _profile_motif("right", style["shape_name"], iris))
        # row 3 / up-facing remains transparent by design.

    alpha = sheet.getchannel("A")
    if alpha.getbbox() is None:
        raise RuntimeError("compiled eye overlay is empty")
    if alpha.crop((0, 3 * CELL, WIDTH, HEIGHT)).getbbox() is not None:
        raise RuntimeError("up-facing row must remain transparent")

    repeat_ok = True
    for row in (0, 1, 2):
        ref = sheet.crop((0, row * CELL, CELL, (row + 1) * CELL))
        for col in (1, 2):
            other = sheet.crop((col * CELL, row * CELL, (col + 1) * CELL, (row + 1) * CELL))
            repeat_ok &= ref.tobytes() == other.tobytes()
    if not repeat_ok:
        raise RuntimeError("movement-phase eye motifs drifted")

    confined = True
    for row in (0, 1, 2):
        for col in range(3):
            cell_alpha = alpha.crop((col * CELL, row * CELL, (col + 1) * CELL, (row + 1) * CELL))
            bbox = cell_alpha.getbbox()
            if bbox is None or bbox[0] < 17 or bbox[2] > 31 or bbox[1] < 2 or bbox[3] > 9:
                confined = False
    if not confined:
        raise RuntimeError("eye pixels escaped locked face-safe window")

    report = {
        "schema": "plushbound.creator_eyes_batch.v1",
        "style_index": style_index,
        "logical_id": style["logical_id"],
        "style": style,
        "dimensions": [WIDTH, HEIGHT],
        "layout": "3x4-48px",
        "mode": "RGBA",
        "direction_rows": ["down", "left", "right", "up"],
        "step_phases": ["left", "idle", "right"],
        "runtime_role": "direct_rgba_overlay",
        "deterministic": True,
        "paid_render_count": 0,
        "paid_extraction_count": 0,
        "validation": {
            "nonempty": True,
            "up_row_empty": True,
            "movement_phase_repeat_consistent": True,
            "face_safe_window_confined": True,
        },
        "requires_locked_body_visual_qc": True,
        "catalog_wide_launch_authorized": False,
    }
    return sheet, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style-index", type=int, required=True)
    parser.add_argument("--output-root", default="creator-eyes-batch-output")
    args = parser.parse_args()

    sheet, report = compile_style(args.style_index)
    root = Path(args.output_root) / f"style-{args.style_index:03d}"
    root.mkdir(parents=True, exist_ok=True)
    png = root / f"creator-eyes-{args.style_index:03d}.png"
    sheet.save(png, optimize=True)
    report["sha256"] = hashlib.sha256(png.read_bytes()).hexdigest()
    (root / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (root / "catalog_snapshot.json").write_text(json.dumps(snapshot(), indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
