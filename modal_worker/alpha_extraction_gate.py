"""Deterministic quality gate for subject/background extraction outputs.

This does not pretend to perform semantic segmentation. It validates the RGBA
result produced by a real extraction backend before normalization/packaging.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image


@dataclass(frozen=True)
class AlphaGatePolicy:
    min_foreground_fraction: float = 0.03
    max_foreground_fraction: float = 0.92
    min_bbox_width_fraction: float = 0.08
    min_bbox_height_fraction: float = 0.12
    edge_alpha_limit: float = 0.35


def inspect_extracted_png(raw: bytes, policy: AlphaGatePolicy = AlphaGatePolicy()) -> dict[str, Any]:
    errors: list[str] = []
    try:
        image = Image.open(BytesIO(raw)); image.load()
    except Exception as exc:
        return {"accepted": False, "errors": [f"invalid PNG/image: {exc}"]}
    if image.format != "PNG": errors.append("extraction output must be PNG")
    rgba = image.convert("RGBA"); alpha = rgba.getchannel("A"); w, h = rgba.size
    hist = alpha.histogram(); total = w * h
    nonzero = total - hist[0]
    foreground_fraction = nonzero / total if total else 0.0
    bbox = alpha.getbbox()
    if bbox is None:
        errors.append("alpha mask contains no foreground")
        bbox_w = bbox_h = 0
    else:
        bbox_w = bbox[2] - bbox[0]; bbox_h = bbox[3] - bbox[1]
    if foreground_fraction < policy.min_foreground_fraction: errors.append("foreground mask is implausibly small")
    if foreground_fraction > policy.max_foreground_fraction: errors.append("background removal left too much opaque image")
    if w and bbox_w / w < policy.min_bbox_width_fraction: errors.append("foreground bounding box is too narrow")
    if h and bbox_h / h < policy.min_bbox_height_fraction: errors.append("foreground bounding box is too short")

    edge_pixels = []
    if w and h:
        edge_pixels.extend(alpha.crop((0, 0, w, 1)).getdata()); edge_pixels.extend(alpha.crop((0, h-1, w, h)).getdata())
        if h > 2:
            edge_pixels.extend(alpha.crop((0, 1, 1, h-1)).getdata()); edge_pixels.extend(alpha.crop((w-1, 1, w, h-1)).getdata())
    edge_alpha_fraction = sum(1 for value in edge_pixels if value > 0) / len(edge_pixels) if edge_pixels else 0.0
    if edge_alpha_fraction > policy.edge_alpha_limit: errors.append("foreground touches too much of the canvas edge")

    return {
        "accepted": not errors, "errors": errors, "width": w, "height": h,
        "foreground_fraction": round(foreground_fraction, 6),
        "bbox": list(bbox) if bbox else None,
        "bbox_width_fraction": round(bbox_w / w, 6) if w else 0.0,
        "bbox_height_fraction": round(bbox_h / h, 6) if h else 0.0,
        "edge_alpha_fraction": round(edge_alpha_fraction, 6),
    }
