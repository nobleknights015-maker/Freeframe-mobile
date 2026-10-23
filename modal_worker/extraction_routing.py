"""Deterministic extraction routing for Plushbound production asset classes.

Only subject-like masters require semantic background removal. Environments must
retain their full scene, while sprite/tileset masters are downstream composites
and therefore bypass this stage.
"""
from __future__ import annotations

EXTRACTION_REQUIRED_CLASSES = frozenset({
    "character_master",
    "guardian_master",
    "enemy_master",
    "portrait_master",
    "icon_master",
})

EXTRACTION_BYPASS_CLASSES = frozenset({
    "environment_master",
    "sprite_master",
    "tileset_master",
})

KNOWN_ASSET_CLASSES = EXTRACTION_REQUIRED_CLASSES | EXTRACTION_BYPASS_CLASSES


def requires_subject_extraction(asset_class: str) -> bool:
    """Return whether an asset class must pass through subject extraction.

    Unknown classes are rejected instead of silently bypassing extraction; this
    keeps newly introduced production classes from accidentally shipping opaque
    backgrounds.
    """
    normalized = asset_class.strip() if isinstance(asset_class, str) else ""
    if not normalized:
        raise ValueError("asset_class must not be empty")
    if normalized not in KNOWN_ASSET_CLASSES:
        raise ValueError(f"unknown production asset class: {normalized}")
    return normalized in EXTRACTION_REQUIRED_CLASSES


def extraction_route(asset_class: str) -> str:
    return "extract_subject" if requires_subject_extraction(asset_class) else "bypass"
