"""Opt-in zero-GPU readability rescue for valid dark A5 material sources.

This does not replace the normalizer and is never automatic. It may only be used
for a source that already passed semantic/manual material QA, contains substantial
source-level RGB variation, and failed only because the normalizer exhausted its
2.0 contrast cap below the locked final RGB stddev threshold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageEnhance

from modal_worker.tileset_source_normalizer import (
    MAX_EDGE_DISCONTINUITY,
    MIN_RGB_STDDEV,
    READABILITY_RESCUE_MAX_CONTRAST,
    _normalize_with_metrics,
    edge_discontinuity,
    rgb_stddev,
)

MIN_SOURCE_RGB_STDDEV = 6.0
SECOND_STAGE_MAX_TOTAL_CONTRAST = 2.5
TARGET_MARGIN = 1.05


def rescue(source: Path, output: Path) -> dict:
    if not source.is_file():
        raise RuntimeError(f"missing source: {source}")
    with Image.open(source) as image:
        if str(image.format or '').upper() != 'PNG':
            raise RuntimeError('source must be PNG')
        tile, base = _normalize_with_metrics(image)

    source_stddev = float(base['source_rgb_stddev'])
    base_stddev = rgb_stddev(tile)
    prior_factor = float(base['readability_contrast_factor'])

    if source_stddev < MIN_SOURCE_RGB_STDDEV:
        raise RuntimeError('source lacks enough genuine variation for second-stage rescue')
    if base_stddev >= MIN_RGB_STDDEV:
        raise RuntimeError('source already passes normal readability gate; second-stage rescue forbidden')
    if not base['readability_rescue_applied']:
        raise RuntimeError('first-stage readability rescue was not applied')
    if abs(prior_factor - READABILITY_RESCUE_MAX_CONTRAST) > 1e-6:
        raise RuntimeError('first-stage rescue did not exhaust its cap')

    required_secondary = (MIN_RGB_STDDEV / max(base_stddev, 1e-9)) * TARGET_MARGIN
    max_secondary = SECOND_STAGE_MAX_TOTAL_CONTRAST / prior_factor
    secondary_factor = min(required_secondary, max_secondary)
    if secondary_factor <= 1.0:
        raise RuntimeError('invalid second-stage rescue factor')

    rescued = ImageEnhance.Contrast(tile.convert('RGB')).enhance(secondary_factor).convert('RGBA')
    final_stddev = rgb_stddev(rescued)
    edge = edge_discontinuity(rescued)
    total_factor = prior_factor * secondary_factor

    output.parent.mkdir(parents=True, exist_ok=True)
    rescued.save(output, format='PNG')
    raw = output.read_bytes()
    accepted = final_stddev >= MIN_RGB_STDDEV and edge <= MAX_EDGE_DISCONTINUITY
    report = {
        'schema': 'plushbound.tileset_low_light_readability_rescue.v1',
        'accepted': accepted,
        'source_path': str(source),
        'output_path': str(output),
        'source_rgb_stddev': round(source_stddev, 4),
        'minimum_source_rgb_stddev': MIN_SOURCE_RGB_STDDEV,
        'base_normalized_rgb_stddev': round(base_stddev, 4),
        'minimum_final_rgb_stddev': MIN_RGB_STDDEV,
        'first_stage_contrast_factor': round(prior_factor, 6),
        'second_stage_contrast_factor': round(secondary_factor, 6),
        'total_contrast_factor': round(total_factor, 6),
        'maximum_total_contrast_factor': SECOND_STAGE_MAX_TOTAL_CONTRAST,
        'final_rgb_stddev': round(final_stddev, 4),
        'edge_discontinuity': round(edge, 6),
        'maximum_edge_discontinuity': MAX_EDGE_DISCONTINUITY,
        'sha256': hashlib.sha256(raw).hexdigest(),
        'provider_calls': 0,
        'gpu_calls': 0,
        'generation_calls': 0,
        'manual_semantic_qa_required_before_acceptance': True,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = rescue(args.source, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report['accepted']:
        raise RuntimeError('second-stage readability rescue failed locked quality gates')


if __name__ == '__main__':
    main()
