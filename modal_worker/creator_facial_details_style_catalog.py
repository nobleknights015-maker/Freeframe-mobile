"""Stable deterministic Creator Facial Details catalog for 48 global overlays."""
from __future__ import annotations

DETAIL_BASES = (
    ("nose_freckles", "freckles across the nose bridge"),
    ("cheek_freckles", "freckles across both cheeks"),
    ("beauty_mark_left", "small beauty mark on left cheek"),
    ("beauty_mark_right", "small beauty mark on right cheek"),
    ("soft_blush", "soft cheek blush accent"),
    ("under_eye_marks", "subtle under-eye detail"),
    ("cheek_stripe_left", "small decorative cheek stripe on left"),
    ("cheek_stripe_right", "small decorative cheek stripe on right"),
    ("cheek_scar_left", "small healed cheek scar on left"),
    ("cheek_scar_right", "small healed cheek scar on right"),
    ("stitch_accent", "small Plushbound stitch-like cheek accent"),
    ("nose_mark", "small centered nose detail"),
)

DETAIL_LEVELS = (
    ("subtle", 1),
    ("natural", 2),
    ("defined", 3),
    ("bold", 4),
)


def build_catalog() -> tuple[dict, ...]:
    entries=[]
    index=1
    for base_name, base_desc in DETAIL_BASES:
        for level_name, level in DETAIL_LEVELS:
            entries.append({
                "index": index,
                "logical_id": f"creator/facial-details/{index:03d}",
                "style_name": f"{base_name}__{level_name}",
                "base_name": base_name,
                "base_description": base_desc,
                "level_name": level_name,
                "level": level,
                "dimensions": "144x192",
                "layout": "3x4-48px",
                "scope": "global",
                "runtime_role": "direct_rgba_overlay",
                "runtime_tintable": False,
            })
            index += 1
    if len(entries) != 48:
        raise RuntimeError(f"expected 48 facial-detail styles, got {len(entries)}")
    return tuple(entries)


FACIAL_DETAIL_STYLES=build_catalog()


def get_style(index:int)->dict:
    if not 1 <= index <= 48:
        raise ValueError("facial detail style index must be 1..48")
    return FACIAL_DETAIL_STYLES[index-1]


def snapshot()->dict:
    return {
        "schema":"plushbound.creator_facial_details_style_catalog.v1",
        "count":48,
        "family":"creator/facial-details",
        "logical_range":["creator/facial-details/001","creator/facial-details/048"],
        "dimensions":"144x192",
        "layout":"3x4-48px",
        "direction_rows":["down","left","right","up"],
        "step_phases":["left","idle","right"],
        "generation_rule":"deterministic pixel overlay; zero paid renders and zero paid extractions",
        "entries":list(FACIAL_DETAIL_STYLES),
    }
