"""Targeted composition repair for Plush Guardian master generation.

The frozen V3.2 Guardian preset sometimes drifts into a multi-view/model-sheet
layout. This repair keeps the subject semantics intact while replacing studio-like
composition cues with a candid in-world scene that favors one creature and one view.
"""
from __future__ import annotations

from typing import Any

GUARDIAN_COMPOSITION_VERSION = "guardian-single-view-v2"

_SINGLE_VIEW_POSITIVE = (
    "candid in-world fantasy scene, one small companion creature sitting naturally beside a forest path, "
    "one continuous outdoor background, one complete creature body visible once, eye-level camera, "
    "natural three-quarter angle, coherent silhouette, no alternate poses, no secondary views"
)

_SINGLE_VIEW_NEGATIVE = (
    "studio product photo, catalog image, contact sheet, tiled grid, character sheet, creature sheet, model sheet, "
    "turnaround, reference board, presentation board, multiple views, alternate view, alternate pose, pose lineup, "
    "front side back views, triptych, diptych, panels, split screen, inset image, thumbnails, repeated creature, "
    "duplicate creature, cloned creature, second creature"
)


def apply_guardian_composition(request: dict[str, Any]) -> dict[str, Any]:
    """Favor a single candid Guardian scene and record repair provenance."""
    result = dict(request)
    prompt = str(result.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("guardian request prompt must not be empty")

    # Keep the user subject first, then inject the high-priority composition cue
    # before the longer V3.2 rendering language reaches the text-encoder tail.
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
