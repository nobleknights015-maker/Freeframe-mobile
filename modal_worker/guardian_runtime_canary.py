"""Bounded Guardian runtime derivation canary.

Uses an already-accepted Guardian source master, the deployed semantic subject extractor,
and deterministic Atlas packaging. It deliberately derives only assets whose semantics do
not require a new pose/expression. No diffusion generation is performed by this canary.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import modal
from PIL import Image

APP_NAME = "freeframe-guardian-runtime-canary"
EXTRACTOR_APP = "freeframe-worker"
EXTRACTOR_CLASS = "FreeFrameExtractor"
OUT_ROOT = Path("guardian-runtime-canary")

TARGETS = {
    "overworld": (144, 192, 0.10),
    "portrait": (288, 288, 0.04),
    "silhouette": (192, 192, 0.08),
    "battle-idle": (192, 192, 0.08),
    "icon": (96, 96, 0.06),
}
DEFERRED_VISUAL_VARIANTS = [
    "battle-action", "battle-hurt", "bond-expression", "field-interaction", "resting-pose"
]

app = modal.App(APP_NAME)


def _fit_subject(subject: Image.Image, width: int, height: int, margin_fraction: float) -> Image.Image:
    rgba = subject.convert("RGBA")
    bbox = rgba.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError("extracted Guardian contains no alpha foreground")
    crop = rgba.crop(bbox)
    inner_w = max(1, round(width * (1.0 - 2.0 * margin_fraction)))
    inner_h = max(1, round(height * (1.0 - 2.0 * margin_fraction)))
    crop.thumbnail((inner_w, inner_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = (width - crop.width) // 2
    y = (height - crop.height) // 2
    canvas.alpha_composite(crop, (x, y))
    return canvas


def _silhouette(subject: Image.Image, width: int, height: int, margin_fraction: float) -> Image.Image:
    fitted = _fit_subject(subject, width, height, margin_fraction)
    alpha = fitted.getchannel("A")
    out = Image.new("RGBA", fitted.size, (18, 18, 22, 0))
    out.putalpha(alpha)
    return out


def _inspect(image: Image.Image) -> dict:
    rgba = image.convert("RGBA")
    a = rgba.getchannel("A")
    bbox = a.getbbox()
    if bbox is None:
        return {"valid": False, "error": "no foreground"}
    w, h = rgba.size
    hist = a.histogram()
    nonzero = w * h - hist[0]
    fraction = nonzero / (w * h)
    edge = []
    edge.extend(a.crop((0, 0, w, 1)).getdata())
    edge.extend(a.crop((0, h - 1, w, h)).getdata())
    edge.extend(a.crop((0, 0, 1, h)).getdata())
    edge.extend(a.crop((w - 1, 0, w, h)).getdata())
    edge_fraction = sum(v > 0 for v in edge) / len(edge)
    valid = 0.02 <= fraction <= 0.88 and edge_fraction <= 0.02
    return {
        "valid": valid,
        "width": w,
        "height": h,
        "foreground_fraction": round(fraction, 6),
        "edge_alpha_fraction": round(edge_fraction, 6),
        "bbox": list(bbox),
        "has_alpha": True,
    }


@app.local_entrypoint()
def main(master_path: str, guardian_id: int = 1):
    if guardian_id < 1 or guardian_id > 96:
        raise ValueError("guardian_id must be 1..96")
    source_path = Path(master_path)
    raw = source_path.read_bytes()
    with Image.open(io.BytesIO(raw)) as check:
        check.load()
        if check.size != (768, 768):
            raise RuntimeError(f"accepted Guardian master geometry changed: {check.size}")

    extractor = modal.Cls.from_name(EXTRACTOR_APP, EXTRACTOR_CLASS)()
    response = extractor.extract.remote({"image_base64": base64.b64encode(raw).decode("ascii")})
    extracted_raw = base64.b64decode(response["image_base64"], validate=True)
    subject = Image.open(io.BytesIO(extracted_raw)).convert("RGBA")

    out_dir = OUT_ROOT / f"guardian-{guardian_id:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "extracted-subject.png").write_bytes(extracted_raw)

    records = {}
    for name, (w, h, margin) in TARGETS.items():
        image = _silhouette(subject, w, h, margin) if name == "silhouette" else _fit_subject(subject, w, h, margin)
        validation = _inspect(image)
        if not validation["valid"]:
            raise RuntimeError(f"{name} deterministic derivative failed validation: {validation}")
        path = out_dir / f"{name}.png"
        image.save(path, format="PNG")
        records[name] = {
            "logical_id": f"guardian/guardian-{guardian_id:03d}/{name}",
            "path": str(path),
            "derivation": "accepted_master_plus_semantic_extraction",
            "validation": validation,
        }

    report = {
        "schema": "plushbound.guardian_runtime_canary.v1",
        "guardian_id": f"guardian-{guardian_id:03d}",
        "source_master": str(source_path),
        "source_master_geometry": [768, 768],
        "extractor_provider": response.get("provider"),
        "extractor_model": response.get("model"),
        "extractor_metadata": response.get("metadata"),
        "derived_count": len(records),
        "derived": records,
        "deferred_visual_variants": DEFERRED_VISUAL_VARIANTS,
        "diffusion_generation_count": 0,
        "production_authorized": False,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
