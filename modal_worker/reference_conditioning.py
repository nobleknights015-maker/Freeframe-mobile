"""Validated image-reference input for FreeFrame SDXL generation.

This module intentionally keeps reference parsing separate from the Modal worker
so request validation remains cheap, deterministic, and unit-testable without a GPU.
"""
from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass, asdict
from typing import Any, Callable

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
    reference_id: str | None = None

    def metadata(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("image", None)
        return data


def _decode_reference(raw: bytes, *, scale: float, reference_id: str | None = None) -> ReferenceConditioning:
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

    return ReferenceConditioning(
        image=image,
        sha256=hashlib.sha256(raw).hexdigest(),
        width=image.width,
        height=image.height,
        scale=scale,
        reference_id=reference_id,
    )


def parse_reference_conditioning(
    request: dict[str, Any],
    *,
    resolver: Callable[[str], bytes] | None = None,
) -> ReferenceConditioning | None:
    """Decode one optional inline or cached reference image.

    Inline image bytes take precedence. Cached references require an explicit
    resolver so pure unit tests and non-Modal callers cannot accidentally touch
    persistent storage.
    """
    scale = float(request.get("reference_scale", DEFAULT_REFERENCE_SCALE))
    if not 0.0 <= scale <= MAX_REFERENCE_SCALE:
        raise ValueError("reference_scale must be between 0.0 and 1.0")

    encoded = request.get("reference_image_base64")
    if encoded:
        try:
            raw = base64.b64decode(str(encoded), validate=True)
        except Exception as exc:
            raise ValueError("reference_image_base64 must be valid base64") from exc
        return _decode_reference(raw, scale=scale)

    reference_id = request.get("reference_id")
    if reference_id:
        if resolver is None:
            raise ValueError("reference_id requires a reference resolver")
        raw = resolver(str(reference_id))
        reference = _decode_reference(raw, scale=scale, reference_id=str(reference_id))
        if reference.sha256 != str(reference_id):
            raise ValueError("reference_id checksum mismatch")
        return reference

    return None
