"""Runtime inspection callback for generated Plushbound masters.

This module bridges raw FreeFrame generation payloads into the deterministic
production policy. It is intentionally cheap enough to run before expensive
extraction and packaging, so obvious model-sheet/grid outputs are rejected and
retried immediately by batch_executor.run_batch.
"""
from __future__ import annotations

import base64
from io import BytesIO
from typing import Any

from PIL import Image

try:
    from .composition_detector import inspect_panel_grid
    from .production_pipeline import POLICIES, inspect_master
except ImportError:  # direct-module compatibility for local CI/tests
    from composition_detector import inspect_panel_grid
    from production_pipeline import POLICIES, inspect_master

_PRESET_TO_ASSET_CLASS = {
    "plushbound_character": "character_master",
    "plushbound_guardian": "guardian_master",
    "plushbound_enemy": "enemy_master",
    "plushbound_environment": "environment_master",
}


def asset_class_for_item(item: dict[str, Any]) -> str:
    explicit = str(item.get("asset_class") or "").strip()
    if explicit:
        return explicit
    preset = str(item.get("preset") or item.get("style_preset") or "").strip()
    if preset in _PRESET_TO_ASSET_CLASS:
        return _PRESET_TO_ASSET_CLASS[preset]
    profile = str(item.get("profile") or "").strip()
    if profile in POLICIES:
        return profile
    raise ValueError("production item requires a recognized asset_class or preset")


def inspect_generation(item: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    encoded = metadata.get("image_base64")
    if not encoded:
        raise ValueError("generation metadata requires image_base64")
    raw = base64.b64decode(str(encoded), validate=True)

    with Image.open(BytesIO(raw)) as image:
        image.load()
        fmt = str(image.format or "")
        width, height = image.size
        has_alpha = "A" in image.getbands()

    asset_class = asset_class_for_item(item)
    panel = inspect_panel_grid(raw)
    policy_result = inspect_master(
        asset_class=asset_class,
        fmt=fmt,
        width=width,
        height=height,
        has_alpha=has_alpha,
        panel_grid_detected=bool(panel["panel_grid_detected"]),
    ).to_dict()
    return {
        **policy_result,
        "composition_detector": panel,
    }
