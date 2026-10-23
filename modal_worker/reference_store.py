"""Persistent reference-image cache for FreeFrame.

Approved reference images are stored by SHA-256 outside the repository. The
content-addressed ID makes reuse deterministic and prevents path traversal.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from PIL import Image

MAX_REFERENCE_BYTES = 16 * 1024 * 1024
_REFERENCE_ID_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class StoredReference:
    reference_id: str
    sha256: str
    width: int
    height: int
    bytes: int
    format: str

    def metadata(self) -> dict[str, Any]:
        return asdict(self)


def validate_reference_bytes(raw: bytes) -> StoredReference:
    if not raw:
        raise ValueError("reference image must not be empty")
    if len(raw) > MAX_REFERENCE_BYTES:
        raise ValueError("reference image exceeds 16 MiB limit")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            width, height = image.size
            fmt = str(image.format or "UNKNOWN")
    except Exception as exc:
        raise ValueError("reference image must be a readable raster image") from exc
    if width < 64 or height < 64:
        raise ValueError("reference image must be at least 64x64")
    digest = hashlib.sha256(raw).hexdigest()
    return StoredReference(digest, digest, width, height, len(raw), fmt)


def _path(root: str | Path, reference_id: str) -> Path:
    if not _REFERENCE_ID_RE.fullmatch(reference_id):
        raise ValueError("reference_id must be a lowercase SHA-256 hex digest")
    return Path(root) / reference_id


def store_reference_bytes(raw: bytes, root: str | Path) -> StoredReference:
    metadata = validate_reference_bytes(raw)
    path = _path(root, metadata.reference_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, path)
    return metadata


def load_reference_bytes(reference_id: str, root: str | Path) -> bytes:
    path = _path(root, reference_id)
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError(f"unknown reference_id: {reference_id}") from exc
    metadata = validate_reference_bytes(raw)
    if metadata.reference_id != reference_id:
        raise ValueError("stored reference checksum mismatch")
    return raw
