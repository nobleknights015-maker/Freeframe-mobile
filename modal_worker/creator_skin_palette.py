"""Deterministic creator skin-palette assets and body recolor helpers.

This family intentionally uses zero diffusion renders. The 18 creator/skin logical
IDs are body-independent palette/LUT assets. A selected locked creator/body sheet
is recolored through a deterministic exposed-skin mask, preserving the body's
geometry, walk cycle, shading, and neutral gray base underlayer.
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, PngImagePlugin

WIDTH = 144
HEIGHT = 192
CELL = 48
MASK_S_MIN = 0.16
MASK_V_MIN = 0.22
MASK_H_WARM_MAX = 0.16
MASK_H_WRAP_MIN = 0.97
TARGET_BLEND = 0.85
SOURCE_DETAIL_BLEND = 0.15
LUMINANCE_FACTOR_MIN = 0.45
LUMINANCE_FACTOR_MAX = 1.55


@dataclass(frozen=True)
class SkinTone:
    id: str
    name: str
    base_color: str
    undertone: str


SKIN_TONES = (
    SkinTone("creator/skin/001", "porcelain_cool", "#F5D7C3", "cool"),
    SkinTone("creator/skin/002", "porcelain_neutral", "#F2CBAF", "neutral"),
    SkinTone("creator/skin/003", "porcelain_warm", "#EFC2A1", "warm"),
    SkinTone("creator/skin/004", "fair_cool", "#E9B89F", "cool"),
    SkinTone("creator/skin/005", "fair_neutral", "#E3AE8D", "neutral"),
    SkinTone("creator/skin/006", "fair_warm", "#DDA17C", "warm"),
    SkinTone("creator/skin/007", "medium_cool", "#CD9178", "cool"),
    SkinTone("creator/skin/008", "medium_neutral", "#C58769", "neutral"),
    SkinTone("creator/skin/009", "medium_warm", "#BB7959", "warm"),
    SkinTone("creator/skin/010", "tan_olive", "#A96F50", "olive"),
    SkinTone("creator/skin/011", "tan_neutral", "#9E6548", "neutral"),
    SkinTone("creator/skin/012", "tan_warm", "#935B3F", "warm"),
    SkinTone("creator/skin/013", "deep_cool", "#80503F", "cool"),
    SkinTone("creator/skin/014", "deep_neutral", "#744536", "neutral"),
    SkinTone("creator/skin/015", "deep_warm", "#693C2E", "warm"),
    SkinTone("creator/skin/016", "rich_cool", "#55352E", "cool"),
    SkinTone("creator/skin/017", "rich_neutral", "#482C25", "neutral"),
    SkinTone("creator/skin/018", "rich_warm", "#3B241E", "warm"),
)


def _hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"invalid hex color: {value}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def detect_skin_pixels(image: Image.Image) -> list[tuple[int, int]]:
    """Return deterministic exposed-skin candidates from a locked body sheet."""
    rgba = image.convert("RGBA")
    candidates: list[tuple[int, int]] = []
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = rgba.getpixel((x, y))
            if a == 0:
                continue
            h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            warm_hue = h <= MASK_H_WARM_MAX or h >= MASK_H_WRAP_MIN
            if s >= MASK_S_MIN and v >= MASK_V_MIN and warm_hue:
                candidates.append((x, y))
    return candidates


def recolor_body(image: Image.Image, tone: SkinTone) -> Image.Image:
    """Apply a selected skin tone without changing body geometry or alpha."""
    rgba = image.convert("RGBA")
    if rgba.size != (WIDTH, HEIGHT):
        raise ValueError(f"creator body must be {(WIDTH, HEIGHT)}, got {rgba.size}")

    candidates = detect_skin_pixels(rgba)
    if not candidates:
        raise ValueError("no exposed-skin candidates found")

    source = rgba.load()
    lums = [_luminance(source[x, y][:3]) for x, y in candidates]
    median = statistics.median(lums) or 1.0
    target = _hex_rgb(tone.base_color)

    output = rgba.copy()
    out = output.load()
    for (x, y), lum in zip(candidates, lums):
        r, g, b, a = source[x, y]
        factor = max(LUMINANCE_FACTOR_MIN, min(LUMINANCE_FACTOR_MAX, lum / median))
        tr, tg, tb = (max(0, min(255, c * factor)) for c in target)
        out[x, y] = (
            round(TARGET_BLEND * tr + SOURCE_DETAIL_BLEND * r),
            round(TARGET_BLEND * tg + SOURCE_DETAIL_BLEND * g),
            round(TARGET_BLEND * tb + SOURCE_DETAIL_BLEND * b),
            a,
        )
    return output


def build_palette_lut(tone: SkinTone) -> Image.Image:
    """Build the exact 144x192 body-independent LUT carrier for one skin ID."""
    base = _hex_rgb(tone.base_color)
    sheet = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    for row in range(4):
        for col in range(3):
            x0, y0 = col * CELL, row * CELL
            for x in range(CELL):
                factor = 0.55 + (x / (CELL - 1)) * 0.75
                rgb = tuple(max(0, min(255, round(c * factor))) for c in base)
                for y in range(CELL):
                    sheet.putpixel((x0 + x, y0 + y), (*rgb, 255))
    return sheet


def _pnginfo(tone: SkinTone) -> PngImagePlugin.PngInfo:
    info = PngImagePlugin.PngInfo()
    info.add_text("logical_id", tone.id)
    info.add_text("role", "creator_skin_palette_lut")
    info.add_text("tone_name", tone.name)
    info.add_text("base_color", tone.base_color)
    info.add_text("undertone", tone.undertone)
    info.add_text("compositor_mode", "derived_skin_recolor")
    return info


def write_palette_family(out_dir: Path) -> dict:
    """Write all 18 exact LUT PNGs plus a deterministic manifest."""
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    entries = {}
    for index, tone in enumerate(SKIN_TONES, start=1):
        path = assets / f"creator-skin-{index:03d}.png"
        build_palette_lut(tone).save(path, format="PNG", pnginfo=_pnginfo(tone), optimize=False)
        payload = path.read_bytes()
        with Image.open(path) as image:
            image.load()
            if image.size != (WIDTH, HEIGHT) or image.mode != "RGBA":
                raise RuntimeError(f"invalid skin LUT geometry: {path}")
        entries[tone.id] = {
            "file": f"assets/{path.name}",
            "tone_name": tone.name,
            "base_color": tone.base_color,
            "undertone": tone.undertone,
            "role": "palette_lut",
            "compositor_mode": "derived_skin_recolor",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "dimensions": f"{WIDTH}x{HEIGHT}",
            "layout": "3x4-48px",
        }

    manifest = {
        "schema": "plushbound.creator_skin_palette_manifest.v1",
        "family": "creator/skin",
        "status": "DETERMINISTIC_READY",
        "count": len(SKIN_TONES),
        "logical_range": [SKIN_TONES[0].id, SKIN_TONES[-1].id],
        "asset_role": "palette_lut",
        "compositor_mode": "derived_skin_recolor",
        "body_dependency": {
            "family": "creator/body",
            "count": 24,
            "archive_lock": "modal_worker/creator_body_archive_lock.json",
        },
        "mask_rule": {
            "alpha_min": 1,
            "hsv_s_min": MASK_S_MIN,
            "hsv_v_min": MASK_V_MIN,
            "warm_hue_max": MASK_H_WARM_MAX,
            "wrap_hue_min": MASK_H_WRAP_MIN,
            "target_blend": TARGET_BLEND,
            "source_detail_blend": SOURCE_DETAIL_BLEND,
            "luminance_factor_min": LUMINANCE_FACTOR_MIN,
            "luminance_factor_max": LUMINANCE_FACTOR_MAX,
        },
        "paid_renders": 0,
        "paid_extractions": 0,
        "entries": entries,
    }
    (out_dir / "creator_skin_palette_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def validate_body_canary(body_path: Path, tone_id: str, output_path: Path) -> dict:
    tone = next((tone for tone in SKIN_TONES if tone.id == tone_id), None)
    if tone is None:
        raise ValueError(f"unknown skin tone: {tone_id}")
    with Image.open(body_path) as image:
        body = image.convert("RGBA")
        alpha_pixels = sum(1 for px in body.getdata() if px[3] > 0)
        mask_pixels = len(detect_skin_pixels(body))
        recolored = recolor_body(body, tone)
        recolored.save(output_path, format="PNG", optimize=False)
    return {
        "body": str(body_path),
        "skin": tone_id,
        "mask_pixels": mask_pixels,
        "alpha_pixels": alpha_pixels,
        "coverage": round(mask_pixels / alpha_pixels, 4) if alpha_pixels else 0.0,
        "output": str(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="creator-skin-palette-output")
    parser.add_argument("--body", action="append", default=[])
    parser.add_argument("--canary-tone", default="creator/skin/009")
    args = parser.parse_args()

    out_dir = Path(args.out)
    manifest = write_palette_family(out_dir)
    canaries = []
    for index, raw in enumerate(args.body, start=1):
        canary_path = out_dir / f"canary-{index:02d}.png"
        canaries.append(validate_body_canary(Path(raw), args.canary_tone, canary_path))
    print(json.dumps({"manifest": manifest["schema"], "count": manifest["count"], "canaries": canaries}, sort_keys=True))


if __name__ == "__main__":
    main()
