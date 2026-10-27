"""Stable paired front/back creator-hair style catalog.

The ledger contains 96 creator/front-hair and 96 creator/back-hair logical IDs.
This catalog binds matching numeric IDs to one hairstyle so front/back generation
cannot drift into unrelated designs. Hair color is intentionally neutral/tintable;
color selection is a later deterministic recolor concern, not extra diffusion art.
"""
from __future__ import annotations

BASE_STYLES = (
    ("short_swept_crop", "compact short layered crown", "close cropped nape with tidy short rear layers"),
    ("textured_pixie", "airy textured pixie crown", "short feathered pixie back with clean nape"),
    ("ear_length_bob", "smooth ear-length bob crown", "rounded ear-length bob back"),
    ("chin_length_bob", "clean chin-length bob crown", "rounded chin-length bob back"),
    ("shoulder_straight", "sleek shoulder-length straight crown", "straight shoulder-length rear fall"),
    ("long_straight", "sleek long straight crown", "long straight rear fall kept compact to sprite silhouette"),
    ("soft_wave_bob", "soft wavy bob crown", "short softly waved bob back"),
    ("shoulder_waves", "shoulder-length loose-wave crown", "shoulder-length loose waves at back"),
    ("long_waves", "long flowing-wave crown", "long controlled rear waves with compact game-readable silhouette"),
    ("short_curls", "short spring-curl crown", "short rounded curl mass at back"),
    ("shoulder_curls", "shoulder-length defined-curl crown", "defined shoulder curls at back"),
    ("long_curls", "long defined-curl crown", "long controlled curls at back"),
    ("short_coils", "short tight-coil crown", "short rounded tight-coil back"),
    ("medium_coils", "medium tight-coil crown", "medium rounded coil volume at back"),
    ("long_coils", "long coil crown with controlled volume", "long controlled coils at back"),
    ("low_ponytail", "smooth crown feeding a low ponytail", "single low ponytail centered at the nape"),
    ("high_ponytail", "lifted crown feeding a high ponytail", "single high ponytail with compact arc"),
    ("twin_low_tails", "balanced crown feeding twin low tails", "two low tails with compact symmetrical silhouette"),
    ("single_braid", "smooth braided-style crown", "single centered rear braid"),
    ("twin_braids", "balanced braided-style crown", "two compact rear braids"),
    ("rope_twists", "defined rope-twist crown", "medium rear rope twists with readable separation"),
    ("locs_medium", "medium loc crown with clean grouping", "medium grouped locs at back"),
    ("low_bun", "smooth crown feeding a low bun", "compact low bun at the nape"),
    ("layered_shag", "layered shag crown with broken texture", "layered medium shag back with tapered ends"),
)

FRONT_VARIANTS = (
    ("side_swept_fringe", "side-swept fringe crossing part of the forehead"),
    ("center_part", "clean center part with face-framing front sections"),
    ("soft_full_fringe", "soft full fringe with separated readable tips"),
    ("curtain_fringe", "curtain fringe opening at the center with two face-framing sections"),
)

# User-authorized terminal Creator Hair set. These overrides are deliberately
# narrow: only the five final IDs are re-described, preserving all completed IDs.
FINAL_ROLE_OVERRIDES = {
    61: ("long_low_ponytail__side_swept_fringe", "smooth crown feeding a long low ponytail, side-swept fringe crossing part of the forehead", "single long low ponytail centered at the nape with full length readable inside the sprite silhouette"),
    62: ("long_low_ponytail__center_part", "smooth crown feeding a long low ponytail, clean center part with face-framing front sections", "single long low ponytail centered at the nape with full length readable inside the sprite silhouette"),
    66: ("short_high_ponytail__center_part", "lifted crown feeding a short high ponytail, clean center part with face-framing front sections", "single short high ponytail with compact cropped arc"),
    67: ("short_high_ponytail__soft_full_fringe", "lifted crown feeding a short high ponytail, soft full fringe with separated readable tips", "single short high ponytail with compact cropped arc"),
    89: ("low_bun__side_swept_fringe", "smooth crown feeding a low bun, side-swept fringe crossing part of the forehead", "compact low bun at the nape"),
}


def build_catalog() -> tuple[dict, ...]:
    entries = []
    index = 1
    for base_name, crown, back in BASE_STYLES:
        for front_name, front_desc in FRONT_VARIANTS:
            style_name = f"{base_name}__{front_name}"
            if index == 1:
                style_name = "short_side_swept_fringe"
            front_description = f"{crown}, {front_desc}"
            back_description = back
            if index in FINAL_ROLE_OVERRIDES:
                style_name, front_description, back_description = FINAL_ROLE_OVERRIDES[index]
            entries.append({
                "index": index,
                "front_logical_id": f"creator/front-hair/{index:03d}",
                "back_logical_id": f"creator/back-hair/{index:03d}",
                "style_name": style_name,
                "front_description": front_description,
                "back_description": back_description,
                "neutral_source_color": "cool graphite-silver",
                "runtime_tintable": True,
                "accessories_baked_in": False,
            })
            index += 1
    if len(entries) != 96:
        raise RuntimeError(f"expected 96 hair styles, got {len(entries)}")
    return tuple(entries)


HAIR_STYLES = build_catalog()


def get_style(index: int) -> dict:
    if not 1 <= index <= 96:
        raise ValueError("hair style index must be 1..96")
    return HAIR_STYLES[index - 1]


def snapshot() -> dict:
    return {
        "schema": "plushbound.creator_hair_style_catalog.v1",
        "count": len(HAIR_STYLES),
        "front_family": "creator/front-hair",
        "back_family": "creator/back-hair",
        "pairing_rule": "same numeric ID is one hairstyle pair",
        "color_rule": "neutral source hair is deterministic-tintable; do not multiply diffusion assets by hair color",
        "entries": list(HAIR_STYLES),
    }
