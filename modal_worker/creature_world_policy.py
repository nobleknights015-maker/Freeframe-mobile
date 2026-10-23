"""Shared living-fabric creature policy for Plushtopia.

This module is the single semantic contract for native non-human creature families.
It deliberately keeps "creature first, textile second": native creatures should read
as living species whose biology happens to use woven/felt/thread materials, never as
retail toys and never as ordinary flesh-and-fur fantasy animals.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

CREATURE_WORLD_POLICY_VERSION = "living-fabric-ecosystem-v1"

LIVING_FABRIC_BASE_POSITIVE = (
    "a living organism native to Plushtopia whose textile construction is part of its natural biology rather than manufacturing, "
    "creature first and textile second, coherent weight-bearing anatomy and purposeful animal posture, alert expressive gaze, "
    "soft woven or felt-like hide stretched over believable living form, subtle seam lines following musculature and joints, "
    "thread and fiber tufts behaving like fur feathers or whiskers, padded extremities with clear locomotion, "
    "visibly alive in the world rather than posed as an object, explicitly a living species and not a toy doll or manufactured object"
)

LIVING_FABRIC_BASE_NEGATIVE = (
    "retail plush toy, stuffed animal, teddy bear, rag doll, doll, beanbag toy, store-bought plush, plush merchandise, "
    "toy product render, product photography, shelf display, catalog product, vinyl figurine, plastic toy, mascot costume, inert object, "
    "ordinary flesh-and-fur animal, realistic biological mammal, normal wolf, normal fox, normal cat, normal bear, taxidermy"
)


@dataclass(frozen=True)
class CreatureFamilyContract:
    family: str
    positive: str
    negative: str = LIVING_FABRIC_BASE_NEGATIVE

    def metadata(self) -> dict[str, str]:
        return {**asdict(self), "version": CREATURE_WORLD_POLICY_VERSION}


CREATURE_FAMILY_CONTRACTS: dict[str, CreatureFamilyContract] = {
    "guardian_friendly": CreatureFamilyContract(
        family="guardian_friendly",
        positive=(
            "friendly Plush Guardian companion species with approachable creature appeal, clean intact textile hide, "
            "subtle decorative seam markings, soft but anatomically coherent silhouette, expressive face, "
            "elemental or biome traits integrated naturally into the body, lively stance and clear personality"
        ),
    ),
    "guardian_corrupt": CreatureFamilyContract(
        family="guardian_corrupt",
        positive=(
            "a corrupted Plush Guardian that still unmistakably shares the same living-fabric biology as healthy Guardians, "
            "recognizable underlying creature anatomy and lineage, torn seams, frayed cloth, exposed stuffing-like inner fiber at wounds, "
            "faded patches, dirt, moss vines fungus or roots where appropriate, corrupted Thread energy, "
            "damage reads as injury and corruption of a living species rather than a broken toy"
        ),
    ),
    "guardian_boss": CreatureFamilyContract(
        family="guardian_boss",
        positive=(
            "an ancient elite boss-tier corrupted Plush Guardian with the same living-fabric biology as other Guardians, "
            "large imposing silhouette, age and lore significance, layered old patches, major torn seams and exposed inner fiber, "
            "relic-like details, biome-specific growth and powerful corrupted Thread energy, "
            "visually dominant and memorable rather than merely a normal Guardian scaled up"
        ),
    ),
    "enemy_creature": CreatureFamilyContract(
        family="enemy_creature",
        positive=(
            "a wild hostile Plushtopia creature from the same living textile ecosystem, less companion-like and more feral, "
            "woven felt or quilted hide integrated into predatory anatomy, thread tufts behaving like fur or bristles, "
            "natural seam structures and padded musculature, dangerous readable silhouette and believable locomotion, "
            "clearly native to Plushbound rather than an ordinary fantasy animal"
        ),
    ),
}

DEFAULT_CREATURE_FAMILY_BY_PRESET = {
    "plushbound_guardian": "guardian_friendly",
    "plushbound_enemy": "enemy_creature",
}

ALLOWED_CREATURE_FAMILIES_BY_PRESET = {
    "plushbound_guardian": frozenset(
        {"guardian_friendly", "guardian_corrupt", "guardian_boss"}
    ),
    "plushbound_enemy": frozenset({"enemy_creature"}),
}


def get_creature_family_contract(family: str) -> CreatureFamilyContract:
    try:
        return CREATURE_FAMILY_CONTRACTS[family]
    except KeyError as exc:
        raise ValueError(f"unknown creature family: {family}") from exc


def resolve_creature_family(preset_name: str, requested_family: str | None = None) -> str | None:
    allowed = ALLOWED_CREATURE_FAMILIES_BY_PRESET.get(preset_name)
    if allowed is None:
        if requested_family is not None:
            raise ValueError(f"preset {preset_name} does not accept creature_family")
        return None

    family = requested_family or DEFAULT_CREATURE_FAMILY_BY_PRESET[preset_name]
    if family not in allowed:
        raise ValueError(
            f"creature family {family} is not valid for preset {preset_name}"
        )
    return family


def apply_creature_world_policy(
    preset_name: str,
    request: dict[str, Any],
    *,
    creature_family: str | None = None,
) -> dict[str, Any]:
    """Apply the living-fabric ecosystem contract without mutating the input."""
    result = dict(request)
    family = resolve_creature_family(preset_name, creature_family)
    if family is None:
        result["creature_world_policy_applied"] = False
        result["creature_world_policy_version"] = CREATURE_WORLD_POLICY_VERSION
        result["creature_family"] = None
        return result

    prompt = str(result.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("creature request prompt must not be empty")

    contract = get_creature_family_contract(family)
    positive = f"{LIVING_FABRIC_BASE_POSITIVE}, {contract.positive}"
    head, sep, tail = prompt.partition(". ")
    if sep:
        result["prompt"] = f"{head}. {positive}. {tail}"
    else:
        result["prompt"] = f"{prompt}. {positive}"

    existing_negative = str(result.get("negative_prompt", "")).strip()
    result["negative_prompt"] = ", ".join(
        part for part in (existing_negative, contract.negative) if part
    )
    result["creature_world_policy_applied"] = True
    result["creature_world_policy_version"] = CREATURE_WORLD_POLICY_VERSION
    result["creature_family"] = family
    return result
