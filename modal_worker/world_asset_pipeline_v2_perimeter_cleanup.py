"""Declared zero-GPU perimeter cleanup for otherwise-valid V2 material masters.

This transform is only for sources whose material field is semantically valid but whose
outer perimeter contains isolated object cues (for example rivets, a rim, or edge-only
grime). It never changes accepted assets. The operation crops an equal, bounded band
from all four sides, resizes the remaining central material field back to 384x384 with
LANCZOS, then normalizes through the canonical V2 normalizer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageStat

from modal_worker.tileset_source_normalizer import MAX_EDGE_DISCONTINUITY, MIN_RGB_STDDEV, edge_discontinuity, rgb_stddev
from modal_worker.world_asset_pipeline_v2_normalizer import normalize_image

TRANSFORM_ID = "v2-perimeter-crop-v1"
INPUT_SIZE = (384, 384)
MIN_CROP_PIXELS = 8
MAX_CROP_PIXELS = 64


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cleanup_image(image: Image.Image, *, crop_pixels: int) -> Image.Image:
    if image.size != INPUT_SIZE:
        raise RuntimeError(f"V2 perimeter cleanup requires {INPUT_SIZE}, got {image.size}")
    if not isinstance(crop_pixels, int) or isinstance(crop_pixels, bool):
        raise RuntimeError("crop_pixels must be an integer")
    if not MIN_CROP_PIXELS <= crop_pixels <= MAX_CROP_PIXELS:
        raise RuntimeError(f"crop_pixels must be between {MIN_CROP_PIXELS} and {MAX_CROP_PIXELS}")
    left = top = crop_pixels
    right = INPUT_SIZE[0] - crop_pixels
    bottom = INPUT_SIZE[1] - crop_pixels
    if right <= left or bottom <= top:
        raise RuntimeError("crop removes the full source")
    return image.convert("RGB").crop((left, top, right, bottom)).resize(INPUT_SIZE, Image.Resampling.LANCZOS)


def cleanup_file(source: Path, repaired_raw: Path, normalized: Path, *, crop_pixels: int, expected_input_sha256: str | None = None) -> dict:
    if not source.is_file():
        raise RuntimeError(f"missing source: {source}")
    input_sha = _sha256(source)
    if expected_input_sha256 is not None and input_sha != expected_input_sha256:
        raise RuntimeError(f"input SHA mismatch: {input_sha} != {expected_input_sha256}")
    with Image.open(source) as image:
        if str(image.format or "").upper() != "PNG":
            raise RuntimeError("V2 perimeter cleanup input must be PNG")
        repaired = cleanup_image(image, crop_pixels=crop_pixels)
    repaired_raw.parent.mkdir(parents=True, exist_ok=True)
    normalized.parent.mkdir(parents=True, exist_ok=True)
    repaired.save(repaired_raw, format="PNG")
    tile = normalize_image(repaired)
    tile.save(normalized, format="PNG")
    stddev = rgb_stddev(tile)
    edge = edge_discontinuity(tile)
    accepted = stddev >= MIN_RGB_STDDEV and edge <= MAX_EDGE_DISCONTINUITY
    return {
        "schema": "plushbound.world_asset_pipeline_v2_deterministic_repair.v1",
        "status": "PASS_ZERO_GPU_DETERMINISTIC_PERIMETER_CLEANUP" if accepted else "FAIL_DETERMINISTIC_PERIMETER_CLEANUP",
        "transform_id": TRANSFORM_ID,
        "crop_pixels_each_edge": crop_pixels,
        "crop_box": [crop_pixels, crop_pixels, INPUT_SIZE[0] - crop_pixels, INPUT_SIZE[1] - crop_pixels],
        "resize_policy": "central_crop_to_384x384_LANCZOS",
        "input_raw_sha256": input_sha,
        "repaired_raw_sha256": _sha256(repaired_raw),
        "normalized_sha256": _sha256(normalized),
        "repaired_raw_rgb_stddev": round(rgb_stddev(repaired), 4),
        "normalized_rgb_stddev": round(stddev, 4),
        "edge_discontinuity": round(edge, 6),
        "minimum_rgb_stddev": MIN_RGB_STDDEV,
        "maximum_edge_discontinuity": MAX_EDGE_DISCONTINUITY,
        "machine_gate": "PASS" if accepted else "FAIL",
        "manual_visual_gate": "REQUIRED",
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "accepted_asset_mutation": False,
        "catalog_wide_launch_authorized": False,
    }


def self_test() -> dict:
    with tempfile.TemporaryDirectory(prefix="v2-perimeter-cleanup-") as td:
        root = Path(td)
        source = root / "source.png"
        repaired = root / "repaired.png"
        tile = root / "tile.png"
        image = Image.new("RGB", INPUT_SIZE)
        px = image.load()
        for y in range(INPUT_SIZE[1]):
            for x in range(INPUT_SIZE[0]):
                base = 115 + ((x * 7 + y * 11) % 45)
                px[x, y] = (base, base + 4, base + 8)
        # Synthetic perimeter-only object cues. They must disappear when the central
        # field is sampled; the transform is not permitted to invent replacement art.
        for y in range(24):
            for x in range(INPUT_SIZE[0]):
                px[x, y] = (40, 20, 10)
                px[x, INPUT_SIZE[1] - 1 - y] = (40, 20, 10)
        for x in range(24):
            for y in range(INPUT_SIZE[1]):
                px[x, y] = (40, 20, 10)
                px[INPUT_SIZE[0] - 1 - x, y] = (40, 20, 10)
        image.save(source, format="PNG")
        report = cleanup_file(source, repaired, tile, crop_pixels=48)
        if report["machine_gate"] != "PASS":
            raise RuntimeError("V2 perimeter cleanup self-test failed machine gate")
        with Image.open(repaired) as out:
            stat = ImageStat.Stat(out.convert("RGB"))
            if sum(stat.mean) / 3.0 < 80:
                raise RuntimeError("V2 perimeter cleanup retained synthetic dark perimeter")
        return {
            "schema": "plushbound.world_asset_pipeline_v2_perimeter_cleanup_self_test.v1",
            "status": "PASS_ZERO_GPU_V2_PERIMETER_CLEANUP",
            "transform_id": TRANSFORM_ID,
            "crop_pixels": 48,
            "provider_calls": 0,
            "gpu_calls": 0,
            "generation_calls": 0,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--repaired-raw", type=Path)
    parser.add_argument("--normalized", type=Path)
    parser.add_argument("--crop-pixels", type=int, default=48)
    parser.add_argument("--expected-input-sha256")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2, sort_keys=True))
        return
    if args.source is None or args.repaired_raw is None or args.normalized is None:
        raise RuntimeError("cleanup requires --source, --repaired-raw, and --normalized")
    report = cleanup_file(
        args.source,
        args.repaired_raw,
        args.normalized,
        crop_pixels=args.crop_pixels,
        expected_input_sha256=args.expected_input_sha256,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["machine_gate"] != "PASS":
        raise RuntimeError("V2 perimeter cleanup failed deterministic machine gate")


if __name__ == "__main__":
    main()
