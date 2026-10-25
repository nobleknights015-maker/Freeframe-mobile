"""Production bridge: canonical Plushbound enemy masters -> 288x288 RGBA battlers.

This module is intentionally separate from ``plushbound_enemy_runtime_production.py``.
That older module is a deterministic replay/canary fixture and MUST NOT be used as
source imagery for production recovery.

Production invariants:
- consume only verified canonical recovered master PNGs;
- preserve logical IDs 1:1 (10 regions x 64 enemy-battle IDs);
- use the frozen BiRefNet extractor for semantic background removal;
- derive exactly one static 288x288 RGBA battler per source master;
- never diffusion-generate, infer, or substitute a missing production asset;
- fail closed on source hash/provenance/count/geometry/alpha errors.
"""
from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image

REGIONS = (
    "elyndor", "crownweave", "silkspire", "gloamfen", "verdancia",
    "tideglass-coast", "moonpatch-steppe", "sunspool-desert", "cinderreach", "frostlace",
)
MASTER_SIZE = (1024, 768)
TARGET_SIZE = (288, 288)
TARGET_MARGIN = 0.055
EXPECTED_PER_REGION = 64
EXPECTED_TOTAL = len(REGIONS) * EXPECTED_PER_REGION
REQUIRED_MODEL = "black-forest-labs/FLUX.2-klein-4B"
REQUIRED_PRESET = "plushbound_enemy"
REQUIRED_RENDERER = "flux2_klein"
REQUIRED_EXTRACTOR_PROVIDER = "birefnet"
REQUIRED_EXTRACTOR_MODEL = "ZhengPeng7/BiRefNet"


@dataclass(frozen=True)
class MasterRecord:
    asset_id: str
    archive_path: str
    sha256: str
    width: int
    height: int
    model: str
    preset: str
    renderer_route: str


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def expected_asset_ids() -> tuple[str, ...]:
    return tuple(
        f"reg/{region}/enemy-battle/{i:03d}"
        for region in REGIONS
        for i in range(1, EXPECTED_PER_REGION + 1)
    )


def load_recovery_index(path: Path) -> dict[str, MasterRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("masters", payload.get("assets", payload if isinstance(payload, list) else None))
    if not isinstance(rows, list):
        raise RuntimeError("recovery index does not contain a master list")
    records: dict[str, MasterRecord] = {}
    for row in rows:
        record = MasterRecord(
            asset_id=str(row["asset_id"]), archive_path=str(row["archive_path"]),
            sha256=str(row["sha256"]), width=int(row["width"]), height=int(row["height"]),
            model=str(row["model"]), preset=str(row["preset"]), renderer_route=str(row["renderer_route"]),
        )
        if record.asset_id in records:
            raise RuntimeError(f"duplicate recovery asset_id: {record.asset_id}")
        records[record.asset_id] = record
    expected = set(expected_asset_ids())
    actual = set(records)
    if actual != expected:
        missing = sorted(expected - actual); extra = sorted(actual - expected)
        raise RuntimeError(f"recovery ID set mismatch: missing={missing[:5]} extra={extra[:5]}")
    for r in records.values():
        if (r.width, r.height) != MASTER_SIZE:
            raise RuntimeError(f"{r.asset_id}: wrong master geometry {(r.width, r.height)}")
        if (r.model, r.preset, r.renderer_route) != (REQUIRED_MODEL, REQUIRED_PRESET, REQUIRED_RENDERER):
            raise RuntimeError(f"{r.asset_id}: wrong production provenance")
    return records


def validate_master_bytes(record: MasterRecord, raw: bytes) -> None:
    if sha256_bytes(raw) != record.sha256:
        raise RuntimeError(f"{record.asset_id}: source SHA-256 mismatch")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.format != "PNG":
                raise RuntimeError(f"{record.asset_id}: source is not PNG")
            if image.size != MASTER_SIZE:
                raise RuntimeError(f"{record.asset_id}: source geometry {image.size}")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"{record.asset_id}: unreadable source PNG: {exc}") from exc


def inspect_alpha(image: Image.Image) -> dict:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    w, h = rgba.size
    if bbox is None:
        return {"valid": False, "error": "no foreground", "width": w, "height": h}
    hist = alpha.histogram(); total = w * h
    foreground_fraction = (total - hist[0]) / total if total else 0.0
    edge = []
    edge += list(alpha.crop((0, 0, w, 1)).tobytes())
    edge += list(alpha.crop((0, h - 1, w, h)).tobytes())
    edge += list(alpha.crop((0, 0, 1, h)).tobytes())
    edge += list(alpha.crop((w - 1, 0, w, h)).tobytes())
    edge_fraction = sum(v > 0 for v in edge) / len(edge) if edge else 0.0
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    valid = (
        0.03 <= foreground_fraction <= 0.92
        and bw / w >= 0.08 and bh / h >= 0.12
        and edge_fraction <= 0.35
    )
    return {
        "valid": valid, "width": w, "height": h,
        "foreground_fraction": round(foreground_fraction, 6),
        "edge_alpha_fraction": round(edge_fraction, 6), "bbox": list(bbox),
    }


def fit_static_battler(extracted: Image.Image, *, margin: float = TARGET_MARGIN) -> Image.Image:
    """Crop transparent padding and fit one subject onto the 288-square game canvas."""
    rgba = extracted.convert("RGBA")
    gate = inspect_alpha(rgba)
    if not gate["valid"]:
        raise RuntimeError(f"extraction alpha gate failed: {gate}")
    bbox = rgba.getchannel("A").getbbox()
    assert bbox is not None
    subject = rgba.crop(bbox)
    inner = max(1, round(TARGET_SIZE[0] * (1 - 2 * margin)))
    subject.thumbnail((inner, inner), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", TARGET_SIZE, (0, 0, 0, 0))
    x = (TARGET_SIZE[0] - subject.width) // 2
    bottom = round(TARGET_SIZE[1] * margin)
    y = TARGET_SIZE[1] - bottom - subject.height
    if y < round(TARGET_SIZE[1] * margin):
        y = (TARGET_SIZE[1] - subject.height) // 2
    canvas.alpha_composite(subject, (x, y))
    out_gate = inspect_alpha(canvas)
    if not out_gate["valid"] or canvas.size != TARGET_SIZE:
        raise RuntimeError(f"packaged battler gate failed: {out_gate}")
    if out_gate["edge_alpha_fraction"] != 0:
        raise RuntimeError(f"packaged battler touches canvas edge: {out_gate}")
    return canvas


def encode_png(image: Image.Image) -> bytes:
    buf = io.BytesIO(); image.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def derive_one(record: MasterRecord, source_png: bytes, extractor: Callable[[bytes], tuple[bytes, str, str]]) -> tuple[bytes, dict]:
    validate_master_bytes(record, source_png)
    extracted_png, provider, model = extractor(source_png)
    if (provider, model) != (REQUIRED_EXTRACTOR_PROVIDER, REQUIRED_EXTRACTOR_MODEL):
        raise RuntimeError(f"{record.asset_id}: wrong extractor provenance {(provider, model)}")
    try:
        extracted = Image.open(io.BytesIO(extracted_png)).convert("RGBA")
    except Exception as exc:
        raise RuntimeError(f"{record.asset_id}: unreadable extraction PNG: {exc}") from exc
    if extracted.size != MASTER_SIZE:
        raise RuntimeError(f"{record.asset_id}: extractor changed source canvas {extracted.size}")
    packaged = fit_static_battler(extracted)
    raw = encode_png(packaged)
    logical_path = record.asset_id + ".png"
    validation = inspect_alpha(packaged)
    return raw, {
        "asset_id": record.asset_id,
        "source_archive_path": record.archive_path,
        "source_sha256": record.sha256,
        "path": logical_path,
        "width": TARGET_SIZE[0], "height": TARGET_SIZE[1], "mode": "RGBA",
        "sha256": sha256_bytes(raw),
        "extractor_provider": provider, "extractor_model": model,
        "validation": validation,
    }
