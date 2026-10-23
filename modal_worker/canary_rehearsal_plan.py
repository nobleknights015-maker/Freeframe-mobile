"""Minimal four-class production canary before any larger GPU rehearsal.

Exactly one deterministic request is selected from each major Plushbound asset
class. The plan is intentionally fail-closed: it reports which classes still lack
a validated production style and never authorizes the 22k batch.
"""
from __future__ import annotations

from modal_worker.production_request_builder import build_production_request

CANARY_REHEARSAL_VERSION = "plushbound-canary-v1"

_CASES = (
    ("character-canary", "plushbound_character", "adult Elyndor field adventurer with practical layered travel clothes and leather satchel", 9801),
    ("guardian-canary", "plushbound_guardian", "small mossbun plush guardian with leaf-shaped ears and green thread seams", 9802),
    ("enemy-canary", "plushbound_enemy", "mossback woodland prowler, low quadruped forest beast with bark plates and leaf mane", 9803),
    ("environment-canary", "plushbound_environment", "sunny plains of Elyndor with a winding path, wildflowers and distant handcrafted village", 9804),
)


def canary_requests() -> list[dict]:
    items: list[dict] = []
    for asset_id, preset, prompt, seed in _CASES:
        request = build_production_request(preset, prompt, seed=seed)
        items.append({"asset_id": asset_id, "preset": preset, "request": request})
    return items


def canary_readiness() -> dict:
    items = canary_requests()
    blocked = [
        item["preset"]
        for item in items
        if not bool(item["request"].get("production_style_validated"))
    ]
    return {
        "version": CANARY_REHEARSAL_VERSION,
        "count": len(items),
        "presets": [item["preset"] for item in items],
        "blocked_presets": blocked,
        "ready_for_four_gpu_canary": not blocked,
        "full_production_authorized": False,
    }
