"""Targeted composition repair for Plush Guardian master generation.

The Guardian preset can drift into multi-view/model-sheet or product-photo imagery.
This repair keeps the subject semantics intact while putting Klein-critical layout
and 2D illustration constraints directly in the positive prompt. Negative-prompt
terms remain useful for renderers that support them, but are not the only guardrail.
"""
from __future__ import annotations

from typing import Any

GUARDIAN_COMPOSITION_VERSION = "guardian-single-view-v3"

_SINGLE_VIEW_POSITIVE = (
    "single-view 2D illustrated in-world fantasy companion scene, exactly one small Plush Guardian creature, "
    "one complete creature body visible exactly once beside a natural forest path, one continuous outdoor background, "
    "eye-level three-quarter camera, coherent animal anatomy and clean silhouette, handcrafted sewn-fabric character design, "
    "flat illustrated image rather than a photographed toy or physical product, no model-sheet arrangement, no alternate pose, "
    "no turnaround, no inset view, no duplicated creature, no typography or labels"
)

_SINGLE_VIEW_NEGATIVE = (
    "studio product photo, photographed toy, collectible product render, catalog image, contact sheet, tiled grid, "
    "character sheet, creature sheet, model sheet, turnaround, reference board, presentation board, multiple views, "
    "alternate view, alternate pose, pose lineup, front side back views, triptych, diptych, panels, split screen, "
    "inset image, thumbnails, repeated creature, duplicate creature, cloned creature, second creature, text, labels"
)


def apply_guardian_composition(request: dict[str, Any]) -> dict[str, Any]:
    """Favor a single 2D candid Guardian scene and record repair provenance."""
    result = dict(request)
    prompt = str(result.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("guardian request prompt must not be empty")

    subject, sep, remainder = prompt.partition(". ")
    if sep:
        result["prompt"] = f"{subject}. {_SINGLE_VIEW_POSITIVE}. {remainder}"
    else:
        result["prompt"] = f"{prompt}. {_SINGLE_VIEW_POSITIVE}"

    existing_negative = str(result.get("negative_prompt", "")).strip()
    result["negative_prompt"] = ", ".join(
        part for part in (existing_negative, _SINGLE_VIEW_NEGATIVE) if part
    )
    result["guardian_composition_repair"] = True
    result["guardian_composition_version"] = GUARDIAN_COMPOSITION_VERSION
    return result
