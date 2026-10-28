"""Deterministic cleanup for a valid woven-reed source with an unwanted inset perimeter.

This is not generation. It crops the clean central weave from an already generated
384x384 source, removes exactly 48 pixels from each edge, resizes the remaining
288x288 continuous substrate back to 384x384, then delegates final 48x48 geometry
to the locked tileset normalizer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from modal_worker.tileset_source_normalizer import (
    MAX_EDGE_DISCONTINUITY,
    MIN_RGB_STDDEV,
    edge_discontinuity,
    normalize_image,
    rgb_stddev,
)

INPUT_SIZE = (384, 384)
CROP_MARGIN = 48
INNER_SIZE = (288, 288)
REBUILT_SIZE = (384, 384)
NORMALIZED_SIZE = (48, 48)


def cleanup(source: Path, rebuilt_output: Path, normalized_output: Path) -> dict:
    if not source.is_file():
        raise RuntimeError(f"missing reed source: {source}")
    with Image.open(source) as image:
        if str(image.format or '').upper() != 'PNG':
            raise RuntimeError('reed source must be PNG')
        if image.size != INPUT_SIZE:
            raise RuntimeError(f'reed source must be {INPUT_SIZE}, got {image.size}')
        base = image.convert('RGB')
        inner = base.crop((CROP_MARGIN, CROP_MARGIN, INPUT_SIZE[0]-CROP_MARGIN, INPUT_SIZE[1]-CROP_MARGIN))
        if inner.size != INNER_SIZE:
            raise RuntimeError('unexpected reed cleanup inner geometry')
        rebuilt = inner.resize(REBUILT_SIZE, Image.Resampling.LANCZOS)
        normalized = normalize_image(rebuilt)

    rebuilt_output.parent.mkdir(parents=True, exist_ok=True)
    normalized_output.parent.mkdir(parents=True, exist_ok=True)
    rebuilt.save(rebuilt_output, format='PNG')
    normalized.save(normalized_output, format='PNG')

    rebuilt_raw = rebuilt_output.read_bytes()
    normalized_raw = normalized_output.read_bytes()
    stddev = rgb_stddev(normalized)
    edge = edge_discontinuity(normalized)
    accepted = stddev >= MIN_RGB_STDDEV and edge <= MAX_EDGE_DISCONTINUITY
    return {
        'schema': 'plushbound.tileset_reed_border_cleanup.v1',
        'accepted': accepted,
        'source_path': str(source),
        'rebuilt_output_path': str(rebuilt_output),
        'normalized_output_path': str(normalized_output),
        'input_size': list(INPUT_SIZE),
        'crop_margin': CROP_MARGIN,
        'inner_size': list(INNER_SIZE),
        'rebuilt_size': list(REBUILT_SIZE),
        'normalized_size': list(NORMALIZED_SIZE),
        'rebuilt_sha256': hashlib.sha256(rebuilt_raw).hexdigest(),
        'normalized_sha256': hashlib.sha256(normalized_raw).hexdigest(),
        'rgb_stddev': round(stddev, 4),
        'minimum_rgb_stddev': MIN_RGB_STDDEV,
        'edge_discontinuity': round(edge, 6),
        'maximum_edge_discontinuity': MAX_EDGE_DISCONTINUITY,
        'provider_calls': 0,
        'gpu_calls': 0,
        'generation_calls': 0,
        'manual_visual_qa_required': True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--rebuilt-output', type=Path, required=True)
    parser.add_argument('--normalized-output', type=Path, required=True)
    args = parser.parse_args()
    report = cleanup(args.source, args.rebuilt_output, args.normalized_output)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report['accepted']:
        raise RuntimeError('cleaned reed source failed locked readability/continuity gates')


if __name__ == '__main__':
    main()
