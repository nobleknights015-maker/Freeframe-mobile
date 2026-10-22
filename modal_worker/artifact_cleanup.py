"""Conservative cleanup helpers for generated master art.

These operations intentionally avoid semantic edits. They only crop edge bands
that have already been detected/approved as unwanted framing artifacts.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image


def crop_edge_band(png: bytes, *, left: int = 0, top: int = 0, right: int = 0, bottom: int = 0) -> bytes:
    if min(left, top, right, bottom) < 0:
        raise ValueError("crop bands cannot be negative")
    with Image.open(BytesIO(png)) as image:
        image.load()
        rgba = image.convert("RGBA")
        width, height = rgba.size
        if left + right >= width or top + bottom >= height:
            raise ValueError("crop would remove the entire image")
        cleaned = rgba.crop((left, top, width - right, height - bottom))
        output = BytesIO()
        cleaned.save(output, format="PNG", optimize=False)
        return output.getvalue()


def alpha_bbox(png: bytes) -> tuple[int, int, int, int] | None:
    """Return the occupied alpha bounding box for an already-transparent asset."""
    with Image.open(BytesIO(png)) as image:
        alpha = image.convert("RGBA").getchannel("A")
        return alpha.getbbox()
