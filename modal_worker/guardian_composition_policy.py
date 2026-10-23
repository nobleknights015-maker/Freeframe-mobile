"""Family-aware composition control for Plush Guardian master generation."""
from __future__ import annotations

from typing import Any

GUARDIAN_COMPOSITION_VERSION = "guardian-family-composition-v5"

_COMMON = (
    "single-view 2D illustrated in-world fantasy creature scene, exactly one complete living Guardian body visible exactly once, "
    "one continuous natural background, coherent nonhuman anatomy, believable weight and locomotion, active creature behavior, "
    "no model-sheet arrangement, no alternate pose, no turnaround, no inset view, no duplicated creature, no typography or labels"
)

_FAMILY_POSITIVE = {
    "guardian_friendly": (
        "small-to-medium companion creature in a candid alert or moving pose, natural creature eye proportions, "
        "clean readable silhouette and clear locomotor anatomy, approachable without stuffed-toy posture"
    ),
    "guardian_corrupt": (
        "hostile corrupted Guardian in a tense stalking prowling braced or wounded living-creature pose, "
        "the original Guardian body plan remains coherent beneath visible textile damage and corruption"
    ),
    "guardian_boss": (
        "large imposing nonhuman Guardian boss with grounded weight and a dominant creature silhouette, "
        "species-specific anatomy rather than human shoulders chest arms or bodybuilder proportions, "
        "never a gorilla-like biped unless the source species explicitly requires it"
    ),
}

_COMMON_NEGATIVE = (
    "studio product photo, photographed toy, retail plush toy, stuffed animal, teddy bear, rag doll, doll, collectible product render, "
    "shelf merchandise, catalog image, inert plush object, product pedestal, character sheet, model sheet, turnaround sheet, contact sheet, "
    "front side back views, alternate poses, duplicate creature, cloned creature, multiple copies, split panel, grid layout, labels, callouts"
)

_FAMILY_NEGATIVE = {
    "guardian_friendly": "oversized doll eyes, floppy inert toy pose",
    "guardian_corrupt": "ordinary injured cat, ordinary diseased animal, realistic fur coat, broken toy",
    "guardian_boss": "humanoid, human torso, bodybuilder, gorilla, ape, muscular biped, furry werewolf, mascot suit",
}


def apply_guardian_composition(
    request: dict[str, Any],
    *,
    creature_family: str = "guardian_friendly",
) -> dict[str, Any]:
    if creature_family not in _FAMILY_POSITIVE:
        raise ValueError(f"unsupported Guardian composition family: {creature_family}")
    result = dict(request)
    prompt = str(result.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("guardian request prompt must not be empty")
    negative = str(result.get("negative_prompt", "")).strip()
    positive = f"{_COMMON}, {_FAMILY_POSITIVE[creature_family]}"
    head, sep, tail = prompt.partition(". ")
    result["prompt"] = f"{head}. {positive}. {tail}" if sep else f"{prompt}. {positive}"
    result["negative_prompt"] = ", ".join(
        part for part in (negative, _COMMON_NEGATIVE, _FAMILY_NEGATIVE[creature_family]) if part
    )
    result["guardian_composition_repair"] = True
    result["guardian_composition_version"] = GUARDIAN_COMPOSITION_VERSION
    result["guardian_composition_family"] = creature_family
    return result
