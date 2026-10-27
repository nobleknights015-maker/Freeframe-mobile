"""Stable deterministic Creator Mouths catalog for 32 global overlays."""
from __future__ import annotations

MOUTH_SHAPES = (
    ("neutral", "small neutral mouth"),
    ("soft_smile", "soft upward smile"),
    ("bright_smile", "brighter open smile"),
    ("gentle_frown", "subtle downward curve"),
    ("determined", "compact firm expression"),
    ("open_small", "small open mouth"),
    ("pout", "soft rounded pout"),
    ("cat_smile", "playful shallow double-curve smile"),
)

MOUTH_WEIGHTS = (
    ("fine", "light fine line"),
    ("natural", "natural readable line"),
    ("defined", "defined stronger line"),
    ("soft_lip", "soft lip accent"),
)


def build_catalog() -> tuple[dict, ...]:
    entries=[]
    index=1
    for shape_name, shape_desc in MOUTH_SHAPES:
        for weight_name, weight_desc in MOUTH_WEIGHTS:
            entries.append({
                "index": index,
                "logical_id": f"creator/mouths/{index:03d}",
                "style_name": f"{shape_name}__{weight_name}",
                "shape_name": shape_name,
                "shape_description": shape_desc,
                "weight_name": weight_name,
                "weight_description": weight_desc,
                "dimensions": "144x192",
                "layout": "3x4-48px",
                "scope": "global",
                "runtime_role": "direct_rgba_overlay",
                "runtime_tintable": False,
            })
            index += 1
    if len(entries) != 32:
        raise RuntimeError(f"expected 32 mouth styles, got {len(entries)}")
    return tuple(entries)


MOUTH_STYLES=build_catalog()


def get_style(index:int)->dict:
    if not 1 <= index <= 32:
        raise ValueError("mouth style index must be 1..32")
    return MOUTH_STYLES[index-1]


def snapshot()->dict:
    return {
        "schema":"plushbound.creator_mouths_style_catalog.v1",
        "count":32,
        "family":"creator/mouths",
        "logical_range":["creator/mouths/001","creator/mouths/032"],
        "dimensions":"144x192",
        "layout":"3x4-48px",
        "direction_rows":["down","left","right","up"],
        "step_phases":["left","idle","right"],
        "generation_rule":"deterministic pixel overlay; zero paid renders and zero paid extractions",
        "entries":list(MOUTH_STYLES),
    }
