"""Targeted composition repair for Plush Guardian master generation.

V4 keeps Guardians as living in-world species. Textile cues describe their biology,
not a manufactured object, while the layout still blocks model-sheet and product
photography drift.
"""
from __future__ import annotations

from typing import Any

GUARDIAN_COMPOSITION_VERSION = "guardian-single-view-v4"

_SINGLE_VIEW_POSITIVE = (
    "single-view 2D illustrated in-world fantasy companion scene, exactly one small living Plush Guardian creature, "
    "one complete creature body visible exactly once beside a natural forest path, one continuous outdoor background, "
    "eye-level three-quarter camera, coherent animal anatomy, weight-bearing limbs, alert living posture and clean silhouette, "
    "soft textile hide and subtle seam markings integrated naturally into living anatomy, "
    "candid creature behavior rather than object display, no model-sheet arrangement, no alternate pose, "
    "no turnaround, no inset view, no duplicated creature, no typography or labels"
)

_SINGLE_VIEW_NEGATIVE = (
    "studio product photo, photographed toy, retail plush toy, stuffed animal, teddy bear, rag doll, doll, "
    "collectible product render, shelf merchandise, catalog image, inert plush object, product pedestal, "
    "character sheet, model sheet, turnaround sheet, contact sheet, front side back views, alternate poses, "
    "duplicate creature, cloned creature, multiple copies, split panel, grid layout, labels, callouts"
)


def apply_guardian_composition(request: dict[str, Any]) -> dict[str, Any]:
    result = dict(request)
    prompt = str(result.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("guardian request prompt must not be empty")
    negative = str(result.get("negative_prompt", "")).strip()

    head, sep, tail = prompt.partition(". ")
    if sep:
        result["prompt"] = f"{head}. {_SINGLE_VIEW_POSITIVE}. {tail}"
    else:
        result["prompt"] = f"{prompt}. {_SINGLE_VIEW_POSITIVE}"
    result["negative_prompt"] = ", ".join(
        part for part in (negative, _SINGLE_VIEW_NEGATIVE) if part
    )
    result["guardian_composition_repair"] = True
    result["guardian_composition_version"] = GUARDIAN_COMPOSITION_VERSION
    return result
