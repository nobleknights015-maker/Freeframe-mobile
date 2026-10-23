"""Tiny live-GPU validation plan for the production extraction path.

This deliberately selects only current subject-like masters. It exists to prove the
real generation -> BiRefNet -> alpha gate path before any larger production rehearsal.
"""
from __future__ import annotations

from production_presets import PLUSHBOUND_STYLE_VERSION, get_preset
from production_sample_plan import SAMPLES
from extraction_routing import requires_subject_extraction

EXTRACTION_SMOKE_VERSION = "plushbound-extraction-smoke-v2"
SMOKE_ASSET_IDS = ("character_master", "enemy_master")


def extraction_smoke_requests() -> list[dict]:
    by_id = {sample.sample_id: sample for sample in SAMPLES}
    selected: list[dict] = []
    for asset_id in SMOKE_ASSET_IDS:
        sample = by_id[asset_id]
        assert requires_subject_extraction(asset_id)
        request = get_preset(sample.preset).apply(sample.prompt, seed=sample.seed)
        assert request["style_version"] == PLUSHBOUND_STYLE_VERSION
        selected.append({
            "asset_id": asset_id,
            "preset": sample.preset,
            "seed": sample.seed,
            "request": request,
        })
    assert len(selected) == 2
    return selected
