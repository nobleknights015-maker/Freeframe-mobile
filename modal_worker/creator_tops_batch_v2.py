"""Hardened Creator Tops local finishing wrapper.

Vera/FLUX generation remains owned by creator_tops_batch.CreatorTopsBatchRunner.
This wrapper persists every paid render before deterministic local extraction, so
an extraction/compiler failure can never erase already-paid source art.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

from modal_worker import creator_tops_batch as base

app = base.app
OUT_ROOT = base.OUT_ROOT
DIRECTIONS = base.DIRECTIONS
SHEET_W = base.SHEET_W
SHEET_H = base.SHEET_H


def _border_white_extract(encoded: str) -> Image.Image:
    """Remove only near-white background connected to the canvas border.

    Garment whites enclosed by the garment outline are preserved. Final sprite
    alpha is still compiler-owned, so this step only isolates/crops source
    texture and does not define runtime geometry.
    """
    raw = base64.b64decode(encoded, validate=True)
    with Image.open(io.BytesIO(raw)) as im:
        rgb = im.convert("RGB")

    w, h = rgb.size
    pixels = rgb.load()
    seen = bytearray(w * h)
    stack: list[tuple[int, int]] = []

    def candidate(x: int, y: int) -> bool:
        r, g, b = pixels[x, y]
        return r >= 210 and g >= 210 and b >= 210

    def push(x: int, y: int) -> None:
        idx = y * w + x
        if not seen[idx] and candidate(x, y):
            seen[idx] = 1
            stack.append((x, y))

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)

    while stack:
        x, y = stack.pop()
        if x:
            push(x - 1, y)
        if x + 1 < w:
            push(x + 1, y)
        if y:
            push(x, y - 1)
        if y + 1 < h:
            push(x, y + 1)

    alpha = bytearray(b"\xff") * (w * h)
    for idx, is_bg in enumerate(seen):
        if is_bg:
            alpha[idx] = 0

    rgba = rgb.convert("RGBA")
    rgba.putalpha(Image.frombytes("L", (w, h), bytes(alpha)))
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError("deterministic top extraction is empty")
    return rgba.crop(bbox)


@app.local_entrypoint()
def main(style_index: int):
    style_index = int(style_index)
    style = base.get_style(style_index)
    out_dir = Path(OUT_ROOT) / f"style-{style_index:03d}"
    raw_dir = out_dir / "sources" / "raw"
    extracted_dir = out_dir / "sources" / "extracted"
    raw_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    print(f"creator top {style_index:03d}: starting Vera render batch", flush=True)
    remote = base.CreatorTopsBatchRunner().generate.remote(style_index)
    print(f"creator top {style_index:03d}: Vera render batch complete; persisting paid sources", flush=True)

    reference_raw = base64.b64decode(remote["reference_png"], validate=True)
    (out_dir / f"creator-top-{style_index:03d}-reference.png").write_bytes(reference_raw)
    (raw_dir / "reference.png").write_bytes(reference_raw)

    for item in remote["directions"]:
        direction = item["direction"]
        (raw_dir / f"{direction}.png").write_bytes(base64.b64decode(item["png"], validate=True))
    print(f"creator top {style_index:03d}: all five paid renders safely persisted", flush=True)

    pieces = {}
    extraction = []
    for item in remote["directions"]:
        direction = item["direction"]
        print(f"creator top {style_index:03d}: deterministic extract {direction}", flush=True)
        piece = _border_white_extract(item["png"])
        pieces[direction] = piece
        piece.save(extracted_dir / f"{direction}.png", format="PNG", optimize=False)
        extraction.append({
            "direction": direction,
            "seed": item["seed"],
            "seconds": item["seconds"],
            "extracted_size": list(piece.size),
        })

    print(f"creator top {style_index:03d}: compiling locked Engine v1 sheet", flush=True)
    sheet, geometry = base._compile_sheet(style, pieces)
    path = out_dir / f"creator-top-{style_index:03d}.png"
    sheet.save(path, format="PNG", optimize=False)
    if sheet.getchannel("A").getbbox() is None:
        raise RuntimeError("compiled top sheet is empty")

    report = {
        "schema": "plushbound.creator_tops_batch.v1",
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
        "source_art_persisted_before_extraction": True,
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
    (out_dir / "catalog_snapshot.json").write_text(json.dumps(base.snapshot(), indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "schema": report["schema"],
        "style_index": style_index,
        "renders": 5,
        "paid_extractions": 0,
        "raw_sources_persisted": 5,
    }, sort_keys=True), flush=True)
