"""Validated image-reference input for FreeFrame SDXL generation.

This module intentionally keeps reference parsing separate from the Modal worker
so request validation remains cheap, deterministic, and unit-testable without a GPU.
"""
from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass, asdict
from typing import Any

from PIL import Image

MAX_REFERENCE_BYTES = 16 * 1024 * 1024
DEFAULT_REFERENCE_SCALE = 0.35
MAX_REFERENCE_SCALE = 1.0


@dataclass(frozen=True)
class ReferenceConditioning:
    image: Image.Image
    sha256: str
    width: int
    height: int
    scale: float

    def metadata(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("image", None)
        return data


def parse_reference_conditioning(request: dict[str, Any]) -> ReferenceConditioning | None:
    """Decode one optional reference image and validate its influence scale."""
    encoded = request.get("reference_image_base64")
    if not encoded:
        return None

    try:
        raw = base64.b64decode(str(encoded), validate=True)
    except Exception as exc:
        raise ValueError("reference_image_base64 must be valid base64") from exc

    if not raw:
        raise ValueError("reference image must not be empty")
    if len(raw) > MAX_REFERENCE_BYTES:
        raise ValueError("reference image exceeds 16 MiB limit")

    try:
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            image = source.convert("RGB")
    except Exception as exc:
        raise ValueError("reference image must be a readable raster image") from exc

    if image.width < 64 or image.height < 64:
        raise ValueError("reference image must be at least 64x64")

    scale = float(request.get("reference_scale", DEFAULT_REFERENCE_SCALE))
    if not 0.0 <= scale <= MAX_REFERENCE_SCALE:
        raise ValueError("reference_scale must be between 0.0 and 1.0")

    return ReferenceConditioning(
        image=image,
        sha256=hashlib.sha256(raw).hexdigest(),
        width=image.width,
        height=image.height,
        scale=scale,
    )
