"""Persistent reference-image cache for FreeFrame.

Approved reference images are stored by SHA-256 outside the repository. The
content-addressed ID makes reuse deterministic and prevents path traversal.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import tempfile
from dataclasses import asdict, dataclass
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


def validate_reference_integrity(
    metadata: StoredReference,
    *,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
) -> None:
    if expected_sha256 is not None:
        expected = str(expected_sha256).strip().lower()
        if not _REFERENCE_ID_RE.fullmatch(expected):
            raise ValueError("expected_sha256 must be a SHA-256 hex digest")
        if metadata.sha256 != expected:
            raise ValueError("reference image checksum mismatch")
    if expected_bytes is not None:
        try:
            expected_size = int(expected_bytes)
        except (TypeError, ValueError) as exc:
            raise ValueError("expected_bytes must be an integer") from exc
        if expected_size < 0:
            raise ValueError("expected_bytes must be non-negative")
        if metadata.bytes != expected_size:
            raise ValueError("reference image byte count mismatch")


def _path(root: str | Path, reference_id: str) -> Path:
    if not _REFERENCE_ID_RE.fullmatch(reference_id):
        raise ValueError("reference_id must be a lowercase SHA-256 hex digest")
    return Path(root) / reference_id


def _atomic_write(path: Path, raw: bytes) -> None:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def store_reference_bytes(
    raw: bytes,
    root: str | Path,
    *,
    expected_sha256: str | None = None,
    expected_bytes: int | None = None,
) -> StoredReference:
    metadata = validate_reference_bytes(raw)
    validate_reference_integrity(
        metadata,
        expected_sha256=expected_sha256,
        expected_bytes=expected_bytes,
    )
    path = _path(root, metadata.reference_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != raw:
        _atomic_write(path, raw)
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
