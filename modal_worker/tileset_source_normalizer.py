"""Deterministic normalization for generated tileset material masters.

Diffusion creates 384x384 material source art. This module moves the outer wrap seam
to the image center, softens only that internal seam band, and downsamples to the
locked 48x48 engine tile. It never asks the model to determine final tile geometry.

Very fine, legitimate material grain can collapse during 8x downsampling. A bounded
readability rescue is therefore allowed only when the source itself proves meaningful
RGB variation. The final readability threshold is never lowered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageStat

INPUT_SIZE = (384, 384)
OUTPUT_SIZE = (48, 48)
SEAM_BAND = 32
MAX_EDGE_DISCONTINUITY = 0.25
MIN_RGB_STDDEV = 3.0
READABILITY_RESCUE_MIN_SOURCE_RGB_STDDEV = 4.0
READABILITY_RESCUE_MARGIN = 1.05
READABILITY_RESCUE_MAX_CONTRAST = 2.0


def _center_seam_mask(size: tuple[int, int], band: int) -> Image.Image:
    width, height = size
    mask = Image.new("L", size, 0)
    px = mask.load()
    half = max(1, band // 2)
    cx, cy = width // 2, height // 2
    for y in range(height):
        for x in range(width):
            dx = abs(x - cx)
            dy = abs(y - cy)
            if dx <= half or dy <= half:
                vx = max(0.0, 1.0 - dx / half) if dx <= half else 0.0
                vy = max(0.0, 1.0 - dy / half) if dy <= half else 0.0
                px[x, y] = int(round(255 * max(vx, vy)))
    return mask.filter(ImageFilter.GaussianBlur(radius=max(1, band // 8)))


def rgb_stddev(image: Image.Image) -> float:
    stat = ImageStat.Stat(image.convert("RGB"))
    return sum(stat.stddev[:3]) / 3.0


def _normalize_with_metrics(image: Image.Image) -> tuple[Image.Image, dict]:
    if image.size != INPUT_SIZE:
        raise RuntimeError(f"tileset source must be exactly {INPUT_SIZE}, got {image.size}")
    base = image.convert("RGB")
    source_stddev = rgb_stddev(base)

    # Wrapping by half the image makes the new outer boundary an adjacency that
    # originally existed at the source center; the old outer discontinuity moves
    # to the center, where it can be locally blended without touching final edges.
    shifted = ImageChops.offset(base, INPUT_SIZE[0] // 2, INPUT_SIZE[1] // 2)
    blurred = shifted.filter(ImageFilter.GaussianBlur(radius=6.0))
    mask = _center_seam_mask(INPUT_SIZE, SEAM_BAND)
    repaired = Image.composite(blurred, shifted, mask)
    tile = repaired.resize(OUTPUT_SIZE, Image.Resampling.LANCZOS).convert("RGB")

    pre_rescue_stddev = rgb_stddev(tile)
    rescue_eligible = (
        pre_rescue_stddev < MIN_RGB_STDDEV
        and source_stddev >= READABILITY_RESCUE_MIN_SOURCE_RGB_STDDEV
    )
    rescue_applied = False
    contrast_factor = 1.0
    if rescue_eligible:
        contrast_factor = min(
            READABILITY_RESCUE_MAX_CONTRAST,
            max(
                1.0,
                (MIN_RGB_STDDEV / max(pre_rescue_stddev, 1e-9)) * READABILITY_RESCUE_MARGIN,
            ),
        )
        if contrast_factor > 1.0:
            tile = ImageEnhance.Contrast(tile).enhance(contrast_factor)
            rescue_applied = True

    final_stddev = rgb_stddev(tile)
    return tile.convert("RGBA"), {
        "source_rgb_stddev": round(source_stddev, 4),
        "pre_rescue_rgb_stddev": round(pre_rescue_stddev, 4),
        "readability_rescue_eligible": rescue_eligible,
        "readability_rescue_applied": rescue_applied,
        "readability_contrast_factor": round(contrast_factor, 6),
        "final_rgb_stddev": round(final_stddev, 4),
        "readability_rescue_min_source_rgb_stddev": READABILITY_RESCUE_MIN_SOURCE_RGB_STDDEV,
        "readability_rescue_max_contrast": READABILITY_RESCUE_MAX_CONTRAST,
    }


def normalize_image(image: Image.Image) -> Image.Image:
    tile, _ = _normalize_with_metrics(image)
    return tile


def edge_discontinuity(image: Image.Image) -> float:
    rgb = image.convert("RGB")
    width, height = rgb.size
    px = rgb.load()
    total = 0
    count = 0
    for y in range(height):
        for c in range(3):
            total += abs(px[0, y][c] - px[width - 1, y][c])
            count += 1
    for x in range(width):
        for c in range(3):
            total += abs(px[x, 0][c] - px[x, height - 1][c])
            count += 1
    return (total / max(1, count)) / 255.0


def normalize_file(source: Path, output: Path) -> dict:
    if not source.is_file():
        raise RuntimeError(f"missing tileset source master: {source}")
    with Image.open(source) as image:
        fmt = str(image.format or "").upper()
        if fmt != "PNG":
            raise RuntimeError(f"tileset source master must be PNG, got {fmt}")
        tile, rescue = _normalize_with_metrics(image)
    edge = edge_discontinuity(tile)
    stddev = rgb_stddev(tile)
    output.parent.mkdir(parents=True, exist_ok=True)
    tile.save(output, format="PNG")
    raw = output.read_bytes()
    accepted = edge <= MAX_EDGE_DISCONTINUITY and stddev >= MIN_RGB_STDDEV
    return {
        "accepted": accepted,
        "source_path": str(source),
        "output_path": str(output),
        "input_size": list(INPUT_SIZE),
        "output_size": list(OUTPUT_SIZE),
        "output_mode": "RGBA",
        "edge_discontinuity": round(edge, 6),
        "maximum_edge_discontinuity": MAX_EDGE_DISCONTINUITY,
        "rgb_stddev": round(stddev, 4),
        "minimum_rgb_stddev": MIN_RGB_STDDEV,
        **rescue,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "visual_semantic_qa_required": True,
    }


def _synthetic_low_contrast_detail_source() -> Image.Image:
    """Create real fine texture that intentionally collapses under 8x resize."""
    image = Image.new("RGB", INPUT_SIZE)
    px = image.load()
    for y in range(INPUT_SIZE[1]):
        for x in range(INPUT_SIZE[0]):
            fine = ((x * 17 + y * 29 + (x * y) % 11) % 13) - 6
            broad = ((x // 24 + y // 20) % 3) - 1
            px[x, y] = (62 + fine + broad, 61 + fine + broad, 43 + fine + broad)
    return image


def self_test() -> dict:
    with tempfile.TemporaryDirectory(prefix="plushbound-tileset-normalizer-") as td:
        root = Path(td)
        source = root / "source.png"
        output = root / "tile.png"
        image = Image.new("RGB", INPUT_SIZE)
        px = image.load()
        for y in range(INPUT_SIZE[1]):
            for x in range(INPUT_SIZE[0]):
                px[x, y] = (
                    70 + ((x * 5 + y * 3) % 90),
                    95 + ((x * 2 + y * 7) % 80),
                    55 + ((x * 3 + y * 2) % 70),
                )
        image.save(source, format="PNG")
        report = normalize_file(source, output)
        if report["output_size"] != [48, 48] or report["output_mode"] != "RGBA":
            raise RuntimeError("normalizer self-test output geometry failed")
        if report["edge_discontinuity"] > MAX_EDGE_DISCONTINUITY:
            raise RuntimeError("normalizer self-test edge continuity failed")
        if report["rgb_stddev"] < MIN_RGB_STDDEV:
            raise RuntimeError("normalizer self-test produced a flat tile")

        # Verify a detail-bearing, low-contrast source may receive bounded rescue.
        low_source = root / "low-detail.png"
        low_output = root / "low-detail-tile.png"
        _synthetic_low_contrast_detail_source().save(low_source, format="PNG")
        low_report = normalize_file(low_source, low_output)
        if low_report["source_rgb_stddev"] < READABILITY_RESCUE_MIN_SOURCE_RGB_STDDEV:
            raise RuntimeError("rescue fixture does not contain enough genuine source variation")
        if low_report["readability_rescue_applied"] and low_report["readability_contrast_factor"] > READABILITY_RESCUE_MAX_CONTRAST:
            raise RuntimeError("readability rescue exceeded contrast cap")

        # A truly flat source must never be rescued into acceptance.
        flat_source = root / "flat.png"
        flat_output = root / "flat-tile.png"
        Image.new("RGB", INPUT_SIZE, (62, 61, 43)).save(flat_source, format="PNG")
        flat_report = normalize_file(flat_source, flat_output)
        if flat_report["readability_rescue_applied"]:
            raise RuntimeError("flat source was incorrectly granted readability rescue")
        if flat_report["accepted"]:
            raise RuntimeError("flat source incorrectly passed readability gate")

        return {
            "status": "PASS",
            "edge_discontinuity": report["edge_discontinuity"],
            "rgb_stddev": report["rgb_stddev"],
            "output_size": report["output_size"],
            "output_mode": report["output_mode"],
            "readability_rescue_cap": READABILITY_RESCUE_MAX_CONTRAST,
            "flat_source_rejected": True,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps({"schema":"plushbound.tileset_source_normalizer_self_test.v1", **self_test()}, indent=2, sort_keys=True))
        return
    if args.source is None or args.output is None:
        raise RuntimeError("normalization requires --source and --output")
    report = normalize_file(args.source, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["accepted"]:
        raise RuntimeError("normalized tile failed deterministic continuity/readability gate")


if __name__ == "__main__":
    main()
