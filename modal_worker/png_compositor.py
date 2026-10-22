"""Pixel-level deterministic PNG compositing for engine-ready sheets."""
from __future__ import annotations

from io import BytesIO
from typing import Iterable

from PIL import Image

from mv_compositor import GridSpec, validate_cells


def compose_rgba_sheet(spec: GridSpec, cell_pngs: Iterable[bytes]) -> bytes:
    """Compose exact-size transparent PNG cells into a grid without distortion."""
    payloads = list(cell_pngs)
    validate_cells(spec, len(payloads))
    sheet = Image.new("RGBA", (spec.width, spec.height), (0, 0, 0, 0))

    for payload, box in zip(payloads, spec.boxes()):
        with Image.open(BytesIO(payload)) as source:
            source.load()
            cell = source.convert("RGBA")
            expected = (spec.cell_width, spec.cell_height)
            if cell.size != expected:
                raise ValueError(f"cell size must be {expected}, got {cell.size}")
            if "A" not in cell.getbands():
                raise ValueError("cell must contain alpha")
            sheet.alpha_composite(cell, dest=(box[0], box[1]))

    output = BytesIO()
    sheet.save(output, format="PNG", optimize=False)
    return output.getvalue()


def inspect_composite(png_bytes: bytes, spec: GridSpec) -> dict:
    """Verify a composed artifact's exact dimensions, format and alpha channel."""
    with Image.open(BytesIO(png_bytes)) as image:
        image.load()
        return {
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "has_alpha": "A" in image.getbands(),
            "valid": (
                image.format == "PNG"
                and image.size == (spec.width, spec.height)
                and "A" in image.getbands()
            ),
        }
