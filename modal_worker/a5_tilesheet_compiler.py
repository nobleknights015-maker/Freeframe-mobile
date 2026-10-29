"""Deterministic Plushbound A5 tilesheet compiler.

Vera/Modal owns source-art generation only. This compiler owns final runtime
geometry. It never resizes, guesses, or visually infers tile placement.

Locked Engine v1 contract:
- PNG
- 384x768 canvas
- 48x48 cells
- 8 columns x 16 rows
- 128 manifest-addressed slots
- origin (0, 0), no margins or padding
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from PIL import Image

TILE_SIZE = 48
COLUMNS = 8
ROWS = 16
SLOT_COUNT = COLUMNS * ROWS
CANVAS_WIDTH = COLUMNS * TILE_SIZE
CANVAS_HEIGHT = ROWS * TILE_SIZE
COMPILER_VERSION = "plushbound-a5-deterministic-v1"


@dataclass(frozen=True)
class A5Slot:
    slot: int
    asset_id: str
    png: bytes


def _load_exact_tile(raw: bytes, *, asset_id: str) -> Image.Image:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.format != "PNG":
                raise ValueError(f"{asset_id}: tile must be PNG")
            if image.size != (TILE_SIZE, TILE_SIZE):
                raise ValueError(
                    f"{asset_id}: tile must be exactly {TILE_SIZE}x{TILE_SIZE}; got {image.width}x{image.height}"
                )
            if image.mode not in {"RGB", "RGBA"}:
                raise ValueError(f"{asset_id}: tile mode must be RGB or RGBA; got {image.mode}")
            return image.convert("RGBA")
    except OSError as exc:
        raise ValueError(f"{asset_id}: invalid PNG payload") from exc


def validate_manifest(slots: Sequence[A5Slot]) -> None:
    if len(slots) != SLOT_COUNT:
        raise ValueError(f"manifest must contain exactly {SLOT_COUNT} slots; got {len(slots)}")

    numbers = [entry.slot for entry in slots]
    expected = list(range(SLOT_COUNT))
    if numbers != expected:
        raise ValueError("manifest slot order must be exactly 0..127 with no gaps, duplicates, or reordering")

    ids = [entry.asset_id for entry in slots]
    if any(not asset_id.strip() for asset_id in ids):
        raise ValueError("every slot requires a non-empty stable asset_id")
    if len(ids) != len(set(ids)):
        raise ValueError("stable asset_ids must be unique across the A5 manifest")


def compile_a5(slots: Sequence[A5Slot]) -> dict:
    """Compile an exact A5 runtime PNG from already-approved 48x48 runtime tiles.

    This function deliberately performs no resizing, cropping, tile extraction,
    interpolation, layout inference, or reference-pixel promotion.
    """
    validate_manifest(slots)
    canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))

    source_hashes: dict[str, str] = {}
    for entry in slots:
        tile = _load_exact_tile(entry.png, asset_id=entry.asset_id)
        column = entry.slot % COLUMNS
        row = entry.slot // COLUMNS
        x = column * TILE_SIZE
        y = row * TILE_SIZE
        canvas.paste(tile, (x, y))
        source_hashes[entry.asset_id] = hashlib.sha256(entry.png).hexdigest()

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    raw = out.getvalue()

    # Re-open final output to fail closed on any encoder/geometry surprise.
    with Image.open(io.BytesIO(raw)) as check:
        check.load()
        if check.format != "PNG" or check.size != (CANVAS_WIDTH, CANVAS_HEIGHT):
            raise RuntimeError("compiled A5 output violated locked PNG geometry")
        if check.mode not in {"RGB", "RGBA"}:
            raise RuntimeError("compiled A5 output violated locked color mode")

    return {
        "png": raw,
        "metadata": {
            "compiler_version": COMPILER_VERSION,
            "format": "PNG",
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
            "tile_width": TILE_SIZE,
            "tile_height": TILE_SIZE,
            "columns": COLUMNS,
            "rows": ROWS,
            "slot_count": SLOT_COUNT,
            "grid_origin": [0, 0],
            "margins": 0,
            "padding": 0,
            "resized_after_generation": False,
            "layout_inferred_visually": False,
            "reference_sheet_pixels_used_as_runtime_art": False,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source_tile_sha256": source_hashes,
        },
    }


def compile_a5_from_manifest(manifest: Sequence[Mapping[str, object]], tile_pngs: Mapping[str, bytes]) -> dict:
    """Manifest adapter used by World Editor/build tooling.

    Manifest rows must already be in deterministic slot order. Missing assets,
    unexpected slots, or geometry mismatches fail closed instead of guessing.
    """
    slots: list[A5Slot] = []
    for row in manifest:
        if "slot" not in row or "asset_id" not in row:
            raise ValueError("manifest rows require slot and asset_id")
        slot = int(row["slot"])
        asset_id = str(row["asset_id"])
        if asset_id not in tile_pngs:
            raise ValueError(f"missing approved runtime tile for {asset_id}")
        slots.append(A5Slot(slot=slot, asset_id=asset_id, png=tile_pngs[asset_id]))
    return compile_a5(slots)
