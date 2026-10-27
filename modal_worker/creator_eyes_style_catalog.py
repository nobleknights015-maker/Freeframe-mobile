"""Stable Creator Eyes catalog for Plushbound's 48 global eye overlays.

The frozen replacement ledger defines creator/eyes/001..048 as global 144x192
RGBA overlays on the Engine v1 3x4 grid of 48px cells. The ledger does not
assign semantic names, so this catalog binds those stable IDs once to eight
readable eye silhouettes across six iris palettes. No diffusion generation is
required; the tiny runtime-scale features are compiled deterministically.
"""
from __future__ import annotations

EYE_SHAPES = (
    ("soft_almond", "balanced soft almond eye"),
    ("round", "open round eye"),
    ("wide", "slightly wider bright eye"),
    ("narrow_almond", "narrow almond eye"),
    ("upturned", "subtly upturned outer corner"),
    ("downturned_soft", "softly lowered outer corner"),
    ("heroic", "defined upper lash with focused iris"),
    ("doll", "large clear iris with soft lower edge"),
)

IRIS_PALETTES = (
    ("warm_brown", "#76503C"),
    ("hazel", "#8B7B46"),
    ("emerald", "#4F8A63"),
    ("teal", "#478A91"),
    ("sapphire", "#5279B8"),
    ("violet", "#8060A4"),
)


def build_catalog() -> tuple[dict, ...]:
    entries = []
    index = 1
    for shape_name, shape_description in EYE_SHAPES:
        for palette_name, iris_hex in IRIS_PALETTES:
            entries.append({
                "index": index,
                "logical_id": f"creator/eyes/{index:03d}",
                "style_name": f"{shape_name}__{palette_name}",
                "shape_name": shape_name,
                "shape_description": shape_description,
                "palette_name": palette_name,
                "iris_hex": iris_hex,
                "dimensions": "144x192",
                "layout": "3x4-48px",
                "scope": "global",
                "runtime_role": "direct_rgba_overlay",
            })
            index += 1
    if len(entries) != 48:
        raise RuntimeError(f"expected 48 eye styles, got {len(entries)}")
    return tuple(entries)


EYE_STYLES = build_catalog()


def get_style(index: int) -> dict:
    if not 1 <= index <= 48:
        raise ValueError("eye style index must be 1..48")
    return EYE_STYLES[index - 1]


def snapshot() -> dict:
    return {
        "schema": "plushbound.creator_eyes_style_catalog.v1",
        "count": 48,
        "family": "creator/eyes",
        "logical_range": ["creator/eyes/001", "creator/eyes/048"],
        "dimensions": "144x192",
        "layout": "3x4-48px",
        "direction_rows": ["down", "left", "right", "up"],
        "step_phases": ["left", "idle", "right"],
        "color_rule": "six fixed iris palettes are encoded in the 48 stable logical IDs",
        "generation_rule": "deterministic pixel overlay; zero paid renders and zero paid extractions",
        "entries": list(EYE_STYLES),
    }
