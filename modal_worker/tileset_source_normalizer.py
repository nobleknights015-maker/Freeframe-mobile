"""Deterministic normalization for generated tileset material masters.

Diffusion creates 384x384 material source art. This module moves the outer wrap seam
to the image center, softens only that internal seam band, and downsamples to the
locked 48x48 engine tile. It never asks the model to determine final tile geometry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageStat

INPUT_SIZE = (384, 384)
OUTPUT_SIZE = (48, 48)
SEAM_BAND = 32
MAX_EDGE_DISCONTINUITY = 0.25
MIN_RGB_STDDEV = 3.0


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
                # Feather from strongest at the seam to zero at band edge.
                vx = max(0.0, 1.0 - dx / half) if dx <= half else 0.0
                vy = max(0.0, 1.0 - dy / half) if dy <= half else 0.0
                px[x, y] = int(round(255 * max(vx, vy)))
    return mask.filter(ImageFilter.GaussianBlur(radius=max(1, band // 8)))


def normalize_image(image: Image.Image) -> Image.Image:
    if image.size != INPUT_SIZE:
        raise RuntimeError(f"tileset source must be exactly {INPUT_SIZE}, got {image.size}")
    base = image.convert("RGB")
    # Wrapping by half the image makes the new outer boundary an adjacency that
    # originally existed at the source center; the old outer discontinuity moves
    # to the center, where it can be locally blended without touching final edges.
    shifted = ImageChops.offset(base, INPUT_SIZE[0] // 2, INPUT_SIZE[1] // 2)
    blurred = shifted.filter(ImageFilter.GaussianBlur(radius=6.0))
    mask = _center_seam_mask(INPUT_SIZE, SEAM_BAND)
    repaired = Image.composite(blurred, shifted, mask)
    tile = repaired.resize(OUTPUT_SIZE, Image.Resampling.LANCZOS).convert("RGBA")
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


def rgb_stddev(image: Image.Image) -> float:
    stat = ImageStat.Stat(image.convert("RGB"))
    return sum(stat.stddev[:3]) / 3.0


def normalize_file(source: Path, output: Path) -> dict:
    if not source.is_file():
        raise RuntimeError(f"missing tileset source master: {source}")
    with Image.open(source) as image:
        fmt = str(image.format or "").upper()
        if fmt != "PNG":
            raise RuntimeError(f"tileset source master must be PNG, got {fmt}")
        tile = normalize_image(image)
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
        "sha256": hashlib.sha256(raw).hexdigest(),
        "visual_semantic_qa_required": True,
    }


def self_test() -> dict:
    with tempfile.TemporaryDirectory(prefix="plushbound-tileset-normalizer-") as td:
        root = Path(td)
        source = root / "source.png"
        output = root / "tile.png"
        # Synthetic non-flat material-like source with continuous internal variation.
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
        return {
            "status": "PASS",
            "edge_discontinuity": report["edge_discontinuity"],
            "rgb_stddev": report["rgb_stddev"],
            "output_size": report["output_size"],
            "output_mode": report["output_mode"],
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
