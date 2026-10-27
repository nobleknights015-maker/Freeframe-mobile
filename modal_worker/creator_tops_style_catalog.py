"""Self-contained reduced-V1 catalog for Plushbound Creator Tops.

The audit JSON remains in-repo as the human-readable scope record, but this
module intentionally embeds the production constants so Modal remote containers
do not depend on non-Python package data being uploaded.
"""
from __future__ import annotations

import json

SELECTED_IDS = tuple(range(1, 120, 2))
CANARY_IDS = (1, 61, 119)
FAMILY_VARIANTS = ("clean", "layered", "trimmed", "structured", "soft")
DESIGN_FAMILIES = (
    ("plushtopia_everyday", "simple stitched everyday shirts and blouses with clean readable silhouettes"),
    ("victorian_tailored", "waistcoats, high collars, fitted vests, lace-front and structured Victorian-inspired tops"),
    ("japanese_layered", "haori-inspired short layers, wrap fronts, sash-accented tops, restrained festival influence"),
    ("chinese_inspired", "cross-collar and stand-collar tops with knot, piping and brocade-inspired details"),
    ("adventurer_practical", "travel tunics, reinforced shirts, belts, shoulder wraps and field-ready layers"),
    ("artisan_crafter", "apron-front, tool-loop, rolled-sleeve and workshop-inspired upper garments"),
    ("guardian_fanwear", "subtle Guardian motif shirts and jackets without copying unique Guardian bodies"),
    ("regional_festival", "bright celebratory tops using ribbons, trim and regional textile motifs"),
    ("scholar_court", "refined formal shirts, scholar coats, cravats and elegant layered collars"),
    ("rugged_frontier", "weathered overshirts, poncho-cut uppers, utility wraps and sturdy stitched pieces"),
    ("cute_plush", "soft rounded cardigans, puff sleeves, bow accents and handcrafted plush-forward silhouettes"),
    ("neutral_mixmatch", "gender-flexible mix-and-match tops deliberately designed to combine with many bottoms and outerwear"),
)

assert len(SELECTED_IDS) == 60 == len(set(SELECTED_IDS))
assert all(1 <= x <= 120 for x in SELECTED_IDS)
assert set(CANARY_IDS).issubset(SELECTED_IDS)
assert len(DESIGN_FAMILIES) == 12


def snapshot() -> dict:
    styles = []
    for family_index, (family_name, brief) in enumerate(DESIGN_FAMILIES):
        for variant_index, variant in enumerate(FAMILY_VARIANTS):
            slot = family_index * 5 + variant_index
            style_id = SELECTED_IDS[slot]
            styles.append({
                "style_index": style_id,
                "logical_id": f"creator/tops/{style_id:03d}",
                "design_family": family_name,
                "variant": variant,
                "brief": brief,
                "dimensions": [144, 192],
                "layout": "3x4-48px",
                "runtime_role": "character_creator_rgba_overlay",
                "source_art_required": True,
            })
    return {
        "schema": "plushbound.creator_tops_style_catalog.v1",
        "ledger_total": 120,
        "v1_target": 60,
        "selected_ids": list(SELECTED_IDS),
        "canary_ids": list(CANARY_IDS),
        "styles": styles,
        "catalog_wide_launch_authorized": False,
        "scope_source": "embedded production constants mirrored by creator_tops_v1_scope.json",
    }


def get_style(style_index: int) -> dict:
    style_index = int(style_index)
    for style in snapshot()["styles"]:
        if style["style_index"] == style_index:
            return style
    raise ValueError(f"Creator Tops style {style_index:03d} is outside the approved reduced V1 scope")


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, sort_keys=True))
