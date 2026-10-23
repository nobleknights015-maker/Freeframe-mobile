"""Shared living-textile creature policy for Plushtopia.

The core visual order is creature first, textile biology second. Native creatures
must look alive and anatomically functional while their skin/tissue is visibly
woven, quilted, felted, threaded, or fibrous. They must not collapse into either
retail plush toys or ordinary fur-and-flesh fantasy animals.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

CREATURE_WORLD_POLICY_VERSION = "living-fabric-ecosystem-v2"

LIVING_FABRIC_BASE_POSITIVE = (
    "a living fantasy organism native to Plushtopia whose textile tissue is natural biology rather than manufacture, "
    "creature first and textile biology second, coherent nonhuman anatomy with believable weight locomotion joints and posture, "
    "the outer surface is visibly matte woven textile skin with a readable cloth weave rather than animal fur or fuzzy plush pile, "
    "subtle anatomical seams follow muscle groups and joints like natural growth lines instead of outlining toy panels, "
    "thread fibers may form sparse crests whiskers or sensory tufts but never a realistic fur coat, "
    "padded feet claws wings fins or other extremities function as real creature anatomy, alert gaze and active in-world behavior, "
    "clearly alive and self-propelled, never posed as merchandise, never an inert stuffed object"
)

LIVING_FABRIC_BASE_NEGATIVE = (
    "retail plush toy, stuffed animal, teddy bear, rag doll, doll, beanbag toy, store-bought plush, plush merchandise, "
    "toy product render, product photography, shelf display, catalog product, vinyl figurine, plastic toy, mascot costume, inert object, "
    "oversized doll eyes, plastic button eyes, fuzzy synthetic plush pile, realistic fur coat, photoreal animal fur, "
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
            "a friendly original Guardian companion species with agile living-creature proportions, natural-sized expressive eyes, "
            "clean intact woven textile skin and only a few restrained seam lines, clear paws feet wings or other locomotor anatomy, "
            "elemental or biome traits integrated as biological features, curious active behavior and a readable fantasy-creature silhouette, "
            "cute through expression and species design rather than stuffed-toy proportions"
        ),
    ),
    "guardian_corrupt": CreatureFamilyContract(
        family="guardian_corrupt",
        positive=(
            "a corrupted Guardian that unmistakably retains the living anatomy and species language of a healthy Guardian, "
            "matte woven cloth skin remains visible across most of the body instead of fur, torn seams behave like wounds, "
            "tears expose pale tangled thread and cotton-like inner fiber as biological tissue, frayed edges fading dirt and damaged patches, "
            "moss vines fungus or roots can grow through wounds, corrupted Thread energy distorts color and posture, "
            "the creature remains alive and dangerous rather than resembling a broken toy or an ordinary diseased animal"
        ),
    ),
    "guardian_boss": CreatureFamilyContract(
        family="guardian_boss",
        positive=(
            "an ancient elite boss-tier Guardian with the same living textile biology, visibly woven cloth skin and anatomical seams, "
            "large nonhuman creature anatomy with believable weight and a dominant species-specific silhouette, never a muscular human-shaped bodybuilder, "
            "old repairs layered into living tissue, major torn seams exposing fibrous inner tissue, relic-like growths and biome-specific features, "
            "powerful corrupted Thread energy, age and lore significance, visually a major living creature rather than a giant toy"
        ),
        negative=LIVING_FABRIC_BASE_NEGATIVE + (
            ", humanoid, human torso, bodybuilder anatomy, gorilla, ape, muscular biped, furry werewolf, anthropomorphic mascot"
        ),
    ),
    "enemy_creature": CreatureFamilyContract(
        family="enemy_creature",
        positive=(
            "a wild hostile Plushtopia species from the same living textile ecosystem, feral and predatory rather than companion-like, "
            "matte woven quilted or layered textile skin is visibly biological across the whole body, sparse thread bristles replace ordinary fur, "
            "natural seam structures follow musculature, believable low animal locomotion and dangerous readable silhouette, "
            "original monster anatomy clearly native to Plushbound rather than a normal real-world animal dressed in fabric"
        ),
    ),
}

DEFAULT_CREATURE_FAMILY_BY_PRESET = {
    "plushbound_guardian": "guardian_friendly",
    "plushbound_enemy": "enemy_creature",
}

ALLOWED_CREATURE_FAMILIES_BY_PRESET = {
    "plushbound_guardian": frozenset({"guardian_friendly", "guardian_corrupt", "guardian_boss"}),
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
        raise ValueError(f"creature family {family} is not valid for preset {preset_name}")
    return family


def apply_creature_world_policy(
    preset_name: str,
    request: dict[str, Any],
    *,
    creature_family: str | None = None,
) -> dict[str, Any]:
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
    result["prompt"] = f"{head}. {positive}. {tail}" if sep else f"{prompt}. {positive}"
    existing_negative = str(result.get("negative_prompt", "")).strip()
    result["negative_prompt"] = ", ".join(part for part in (existing_negative, contract.negative) if part)
    result["creature_world_policy_applied"] = True
    result["creature_world_policy_version"] = CREATURE_WORLD_POLICY_VERSION
    result["creature_family"] = family
    return result
