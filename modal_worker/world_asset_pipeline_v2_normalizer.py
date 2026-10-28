"""World Asset Pipeline V2 deterministic finishing policy.

Reuses the proven seam-repair/downsample normalizer, then allows one additional
bounded low-light readability rescue only when genuine source variation exists and
the first-stage output still falls below the unchanged 3.0 RGB-stddev gate.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance

from modal_worker.tileset_source_normalizer import (
    MAX_EDGE_DISCONTINUITY,
    MIN_RGB_STDDEV,
    READABILITY_RESCUE_MIN_SOURCE_RGB_STDDEV,
    edge_discontinuity,
    normalize_image as _stage1_normalize,
    rgb_stddev,
)

V2_SECOND_STAGE_MAX_CONTRAST = 1.25
V2_READABILITY_MARGIN = 1.05


def normalize_image(image: Image.Image) -> Image.Image:
    source_stddev = rgb_stddev(image)
    tile = _stage1_normalize(image).convert("RGBA")
    first_stage_stddev = rgb_stddev(tile)
    if (
        first_stage_stddev < MIN_RGB_STDDEV
        and source_stddev >= READABILITY_RESCUE_MIN_SOURCE_RGB_STDDEV
    ):
        factor = min(
            V2_SECOND_STAGE_MAX_CONTRAST,
            max(1.0, (MIN_RGB_STDDEV / max(first_stage_stddev, 1e-9)) * V2_READABILITY_MARGIN),
        )
        if factor > 1.0:
            tile = ImageEnhance.Contrast(tile.convert("RGB")).enhance(factor).convert("RGBA")
    return tile


def metrics(image: Image.Image) -> dict:
    tile = normalize_image(image)
    return {
        "rgb_stddev": round(rgb_stddev(tile), 4),
        "edge_discontinuity": round(edge_discontinuity(tile), 6),
        "accepted": rgb_stddev(tile) >= MIN_RGB_STDDEV and edge_discontinuity(tile) <= MAX_EDGE_DISCONTINUITY,
    }


def _low_light_fixture() -> Image.Image:
    image = Image.new("RGB", (384, 384))
    px = image.load()
    amplitude = 19
    for y in range(384):
        for x in range(384):
            fine = ((x * 17 + y * 29 + (x * y) % 17) % (2 * amplitude + 1)) - amplitude
            broad = ((x // 24 + y // 20) % 3) - 1
            px[x, y] = (62 + fine + broad, 61 + fine + broad, 43 + fine + broad)
    return image


def self_test() -> dict:
    fixture = _low_light_fixture()
    stage1 = _stage1_normalize(fixture)
    stage1_stddev = rgb_stddev(stage1)
    if stage1_stddev >= MIN_RGB_STDDEV:
        raise RuntimeError("V2 low-light fixture no longer exercises second-stage rescue")
    final = normalize_image(fixture)
    final_stddev = rgb_stddev(final)
    edge = edge_discontinuity(final)
    if final_stddev < MIN_RGB_STDDEV or edge > MAX_EDGE_DISCONTINUITY:
        raise RuntimeError("V2 low-light rescue failed locked readability/continuity gates")

    flat = Image.new("RGB", (384, 384), (62, 61, 43))
    flat_final = normalize_image(flat)
    if rgb_stddev(flat_final) >= MIN_RGB_STDDEV:
        raise RuntimeError("V2 incorrectly rescued a flat source")

    return {
        "schema": "plushbound.world_asset_pipeline_v2_normalizer_self_test.v1",
        "status": "PASS_ZERO_GPU_V2_NORMALIZER",
        "stage1_fixture_rgb_stddev": round(stage1_stddev, 4),
        "v2_fixture_rgb_stddev": round(final_stddev, 4),
        "v2_fixture_edge_discontinuity": round(edge, 6),
        "minimum_rgb_stddev": MIN_RGB_STDDEV,
        "maximum_edge_discontinuity": MAX_EDGE_DISCONTINUITY,
        "second_stage_max_contrast": V2_SECOND_STAGE_MAX_CONTRAST,
        "flat_source_rejected": True,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
    }


if __name__ == "__main__":
    print(json.dumps(self_test(), indent=2, sort_keys=True))
