"""Deterministic reduced-V1 catalog for Plushbound Creator Tops.

The selected logical IDs are intentionally distributed across the authoritative
001-120 ledger.  V1 contains exactly 60 tops; this module never authorizes the
unselected 60 IDs.
"""
from __future__ import annotations

import json
from pathlib import Path

_SCOPE = Path(__file__).with_name("creator_tops_v1_scope.json")
_FAMILY_VARIANTS = (
    "clean", "layered", "trimmed", "structured", "soft",
)


def _load_scope() -> dict:
    data = json.loads(_SCOPE.read_text())
    assert data["schema"] == "plushbound.creator_tops_v1_scope.v1"
    assert data["family"] == "creator/tops"
    assert data["ledger_total"] == 120 and data["v1_target"] == 60
    ids = [int(x) for x in data["selected_ids"]]
    assert len(ids) == 60 == len(set(ids))
    assert all(1 <= x <= 120 for x in ids)
    assert set(data["canary_ids"]).issubset(ids)
    families = data["design_families"]
    assert len(families) == 12 and all(int(x["count"]) == 5 for x in families)
    return data


def snapshot() -> dict:
    scope = _load_scope()
    styles = []
    ids = scope["selected_ids"]
    for family_index, family in enumerate(scope["design_families"]):
        for variant_index in range(5):
            slot = family_index * 5 + variant_index
            style_id = int(ids[slot])
            styles.append({
                "style_index": style_id,
                "logical_id": f"creator/tops/{style_id:03d}",
                "design_family": family["name"],
                "variant": _FAMILY_VARIANTS[variant_index],
                "brief": family["brief"],
                "dimensions": [144, 192],
                "layout": "3x4-48px",
                "runtime_role": "character_creator_rgba_overlay",
                "source_art_required": True,
            })
    return {
        "schema": "plushbound.creator_tops_style_catalog.v1",
        "ledger_total": 120,
        "v1_target": 60,
        "selected_ids": ids,
        "canary_ids": scope["canary_ids"],
        "styles": styles,
        "catalog_wide_launch_authorized": False,
    }


def get_style(style_index: int) -> dict:
    style_index = int(style_index)
    for style in snapshot()["styles"]:
        if style["style_index"] == style_index:
            return style
    raise ValueError(f"Creator Tops style {style_index:03d} is outside the approved reduced V1 scope")


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=2, sort_keys=True))
