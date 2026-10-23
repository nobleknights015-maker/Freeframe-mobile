"""Minimal four-class production canary before any larger GPU rehearsal.

Exactly one deterministic request is selected from each major Plushbound asset
class. The plan is intentionally fail-closed: every asset class needs a validated
production style and the character lane needs an explicitly validated style lock
before any paid four-image canary may run. Passing never authorizes the 22k batch.
"""
from __future__ import annotations

from modal_worker.production_request_builder import build_production_request

CANARY_REHEARSAL_VERSION = "plushbound-canary-v2"
CHARACTER_STYLE_LOCK_BLOCKER = "plushbound_character_style_lock"

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


def canary_readiness(*, character_style_lock_ready: bool = False) -> dict:
    items = canary_requests()
    blocked = [
        item["preset"]
        for item in items
        if not bool(item["request"].get("production_style_validated"))
    ]
    if not character_style_lock_ready:
        blocked.append(CHARACTER_STYLE_LOCK_BLOCKER)
    blocked = list(dict.fromkeys(blocked))
    return {
        "version": CANARY_REHEARSAL_VERSION,
        "count": len(items),
        "presets": [item["preset"] for item in items],
        "blocked_presets": blocked,
        "character_style_lock_ready": bool(character_style_lock_ready),
        "ready_for_four_gpu_canary": not blocked,
        "full_production_authorized": False,
    }
