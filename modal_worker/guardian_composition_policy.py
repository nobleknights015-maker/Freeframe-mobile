"""Targeted composition repair for Plush Guardian master generation.

The frozen V3.2 Guardian preset sometimes drifts into a multi-view/model-sheet
layout. This repair keeps the subject semantics intact while strengthening the
single-creature, single-camera composition without changing other asset classes.
"""
from __future__ import annotations

from typing import Any

GUARDIAN_COMPOSITION_VERSION = "guardian-single-view-v1"

_SINGLE_VIEW_POSITIVE = (
    "one finished creature illustration, exactly one creature, exactly one body, one pose, one camera view, "
    "front three-quarter view, full creature visible at once, centered in one continuous scene, "
    "single coherent silhouette, no alternate poses and no secondary views"
)

_SINGLE_VIEW_NEGATIVE = (
    "character sheet, creature sheet, model sheet, turnaround, reference board, presentation board, "
    "multiple views, alternate view, alternate pose, pose lineup, front side back views, triptych, diptych, "
    "panels, split screen, inset image, thumbnails, repeated creature, duplicate creature, cloned creature"
)


def apply_guardian_composition(request: dict[str, Any]) -> dict[str, Any]:
    """Strengthen single-view Guardian composition and record provenance."""
    result = dict(request)
    prompt = str(result.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("guardian request prompt must not be empty")

    # Preserve the subject phrase at the front, then immediately reinforce the
    # composition contract before the longer V3.2 rendering language.
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
