"""Deterministic image normalization before MV packaging.

This module performs geometry-only operations: convert to RGBA, optionally crop
transparent margins, resize while preserving aspect ratio, and pad onto an exact
transparent canvas. It never invents pixels or performs semantic edits.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image


def normalize_rgba_cell(
    png: bytes,
    *,
    target_width: int,
    target_height: int,
    crop_transparent: bool = True,
    padding: int = 0,
) -> tuple[bytes, dict]:
    if target_width <= 0 or target_height <= 0:
        raise ValueError("target dimensions must be positive")
    if padding < 0 or padding * 2 >= min(target_width, target_height):
        raise ValueError("padding is invalid for target dimensions")

    with Image.open(BytesIO(png)) as source:
        source.load()
        image = source.convert("RGBA")
        original_size = image.size

        crop_box = None
        if crop_transparent:
            crop_box = image.getchannel("A").getbbox()
            if crop_box is None:
                raise ValueError("source contains no visible pixels")
            image = image.crop(crop_box)

        available_w = target_width - padding * 2
        available_h = target_height - padding * 2
        scale = min(available_w / image.width, available_h / image.height)
        new_w = max(1, min(available_w, round(image.width * scale)))
        new_h = max(1, min(available_h, round(image.height * scale)))
        resized = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 0))
        x = (target_width - new_w) // 2
        y = (target_height - new_h) // 2
        canvas.alpha_composite(resized, dest=(x, y))

        output = BytesIO()
        canvas.save(output, format="PNG", optimize=False)
        metadata = {
            "original_size": list(original_size),
            "crop_box": list(crop_box) if crop_box is not None else None,
            "resized_size": [new_w, new_h],
            "target_size": [target_width, target_height],
            "placement": [x, y],
            "padding": padding,
            "operation": "rgba_contain_center",
        }
        return output.getvalue(), metadata
