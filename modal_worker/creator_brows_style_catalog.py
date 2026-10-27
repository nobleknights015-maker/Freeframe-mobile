"""Stable deterministic Creator Brows catalog for 32 global overlays."""
from __future__ import annotations

BROW_SHAPES = (
    ("soft_arch", "balanced soft arch"),
    ("straight", "clean straight brow"),
    ("gentle_angle", "gentle angled brow"),
    ("high_arch", "higher elegant arch"),
    ("low_arch", "low relaxed arch"),
    ("tapered", "tapered outer brow"),
    ("rounded", "soft rounded brow"),
    ("determined", "slightly determined inward angle"),
)

BROW_WEIGHTS = (
    ("fine", "light fine weight"),
    ("natural", "natural medium weight"),
    ("defined", "defined medium-full weight"),
    ("bold", "bold full weight"),
)


def build_catalog() -> tuple[dict, ...]:
    entries=[]
    index=1
    for shape_name, shape_desc in BROW_SHAPES:
        for weight_name, weight_desc in BROW_WEIGHTS:
            entries.append({
                "index": index,
                "logical_id": f"creator/brows/{index:03d}",
                "style_name": f"{shape_name}__{weight_name}",
                "shape_name": shape_name,
                "shape_description": shape_desc,
                "weight_name": weight_name,
                "weight_description": weight_desc,
                "dimensions": "144x192",
                "layout": "3x4-48px",
                "scope": "global",
                "runtime_role": "direct_rgba_overlay",
                "runtime_tintable": True,
                "neutral_source_color": "warm graphite",
            })
            index += 1
    if len(entries) != 32:
        raise RuntimeError(f"expected 32 brow styles, got {len(entries)}")
    return tuple(entries)


BROW_STYLES=build_catalog()


def get_style(index:int)->dict:
    if not 1 <= index <= 32:
        raise ValueError("brow style index must be 1..32")
    return BROW_STYLES[index-1]


def snapshot()->dict:
    return {
        "schema":"plushbound.creator_brows_style_catalog.v1",
        "count":32,
        "family":"creator/brows",
        "logical_range":["creator/brows/001","creator/brows/032"],
        "dimensions":"144x192",
        "layout":"3x4-48px",
        "direction_rows":["down","left","right","up"],
        "step_phases":["left","idle","right"],
        "generation_rule":"deterministic pixel overlay; zero paid renders and zero paid extractions",
        "color_rule":"neutral source brow is runtime tintable",
        "entries":list(BROW_STYLES),
    }
