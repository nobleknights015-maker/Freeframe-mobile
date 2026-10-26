"""Deterministic cross-body QC for creator front-hair overlay sheets.

Use after a front-hair canary/batch artifact is available. The validator composites
one exact 144x192 front-hair overlay over representative locked creator/body sheets
and checks that each hair cell intersects the upper head region without clipping.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

CELL = 48
SIZE = (144, 192)


def _rgba(path: Path) -> Image.Image:
    with Image.open(path) as image:
        out = image.convert("RGBA")
    if out.size != SIZE:
        raise ValueError(f"expected {SIZE} for {path}, got {out.size}")
    return out


def _cell_alpha(image: Image.Image, row: int, col: int) -> Image.Image:
    return image.getchannel("A").crop((col*CELL, row*CELL, (col+1)*CELL, (row+1)*CELL))


def validate_pair(body: Image.Image, hair: Image.Image, body_name: str) -> dict:
    cells = []
    for row in range(4):
        for col in range(3):
            ba = _cell_alpha(body, row, col)
            ha = _cell_alpha(hair, row, col)
            hb = ha.getbbox()
            bb = ba.getbbox()
            if hb is None or bb is None:
                raise RuntimeError(f"empty cell for {body_name} row={row} col={col}")
            if hb[1] > 8:
                raise RuntimeError(f"hair floats too low for {body_name} row={row} col={col}: {hb}")
            if hb[3] > 30:
                raise RuntimeError(f"hair extends below head zone for {body_name} row={row} col={col}: {hb}")

            hair_pixels = 0
            overlap = 0
            # Upper 28px is the creator head/crown validation zone.
            for y in range(0, 28):
                for x in range(CELL):
                    hv = ha.getpixel((x, y))
                    if hv:
                        hair_pixels += 1
                        if ba.getpixel((x, y)):
                            overlap += 1
            ratio = overlap / hair_pixels if hair_pixels else 0.0
            if ratio < 0.08:
                raise RuntimeError(
                    f"hair/head overlap too low for {body_name} row={row} col={col}: {ratio:.4f}"
                )
            cells.append({
                "row": row,
                "col": col,
                "body_bbox": list(bb),
                "hair_bbox": list(hb),
                "hair_head_overlap_ratio": round(ratio, 4),
            })
    return {"body": body_name, "passed": True, "cells": cells}


def build_contact(hair: Image.Image, bodies: list[tuple[str, Image.Image]], out: Path) -> None:
    scale = 3
    pad = 10
    label_h = 24
    tile_w = SIZE[0] * scale
    tile_h = SIZE[1] * scale + label_h
    canvas = Image.new("RGBA", (tile_w * len(bodies), tile_h), (245,245,245,255))
    draw = ImageDraw.Draw(canvas)
    for idx, (name, body) in enumerate(bodies):
        composite = body.copy()
        composite.alpha_composite(hair)
        composite = composite.resize((SIZE[0]*scale, SIZE[1]*scale), Image.Resampling.NEAREST)
        x = idx * tile_w
        canvas.alpha_composite(composite, dest=(x, label_h))
        draw.text((x+4, 4), name, fill=(0,0,0,255))
    canvas.convert("RGB").save(out, format="PNG")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hair", required=True)
    parser.add_argument("--body", action="append", required=True, help="NAME=path/to/body.png")
    parser.add_argument("--report", default="creator-front-hair-cross-body-qc.json")
    parser.add_argument("--contact", default="creator-front-hair-cross-body-contact.png")
    args = parser.parse_args()

    hair = _rgba(Path(args.hair))
    bodies = []
    results = []
    for item in args.body:
        if "=" not in item:
            raise ValueError("--body must be NAME=PATH")
        name, raw = item.split("=", 1)
        body = _rgba(Path(raw))
        bodies.append((name, body))
        results.append(validate_pair(body, hair, name))

    report = {
        "schema": "plushbound.creator_front_hair_cross_body_qc.v1",
        "hair": args.hair,
        "body_count": len(bodies),
        "all_passed": all(r["passed"] for r in results),
        "results": results,
    }
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    build_contact(hair, bodies, Path(args.contact))
    print(json.dumps({"schema": report["schema"], "body_count": len(bodies), "all_passed": report["all_passed"]}, sort_keys=True))


if __name__ == "__main__":
    main()
