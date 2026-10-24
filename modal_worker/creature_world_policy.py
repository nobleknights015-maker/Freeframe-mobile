"""Shared living-textile creature policy for Plushtopia.

The core visual order is creature first, textile biology second. Native creatures
must look alive and functionally built while their exterior is visibly woven,
felted, quilted, threaded, or fibrous. Textile traits are living integument, never
evidence that the subject is a manufactured toy or an anatomical cutaway.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

CREATURE_WORLD_POLICY_VERSION = "living-fabric-ecosystem-v4-enclosed-body"

LIVING_FABRIC_BASE_POSITIVE = (
    "a living fantasy organism native to Plushtopia, creature first and textile biology second, "
    "its textile integument is natural living tissue rather than a sewn manufactured object, "
    "a fully enclosed exterior body with believable mass joints balance weight and locomotion, all internal support structures remain completely hidden beneath the living outer body, "
    "the torso is solid and externally continuous with no visible ribs bones spine skull sockets or anatomical cutaway openings, "
    "limbs taper and bend at functional joints while feet paws claws wings fins or other extremities articulate naturally and interact with the ground or air, "
    "the outer surface is a continuous matte woven felted quilted or thread-fiber dermis that conforms to the living body instead of forming inflated stuffed volumes, "
    "any seam-like growth lines are sparse subtle and surface-level anatomy-following features rather than sewing-pattern borders or openings into the body, "
    "thread fibers may form sensory tufts crests manes or whiskers but never an ordinary realistic fur coat, "
    "eyes are expressive living creature eyes proportionate to the head rather than glossy doll eyes, "
    "alert self-propelled behavior and a species-specific silhouette make the organism read as alive before its textile material is noticed"
)

LIVING_FABRIC_BASE_NEGATIVE = (
    "visible skeleton, exposed bones, exposed ribs, ribcage, visible spine, exposed skull, skull face, skeletal creature, undead creature, zombie anatomy, "
    "anatomical cutaway, anatomy model, x-ray view, transparent torso, hollow torso, missing body wall, bones showing through skin, exposed internal framework, "
    "retail plush toy, stuffed animal, teddy bear, rag doll, doll, beanbag toy, store-bought plush, plush merchandise, "
    "toy product render, product photography, shelf display, catalog product, vinyl figurine, plastic toy, mascot costume, inert object, "
    "oversized doll eyes, plastic button eyes, safety eyes, oversized baby head, mascot proportions, round toy muzzle, "
    "tubular stuffed limbs, inflated padded body, floppy ragdoll posture, sewing-pattern panel silhouette, fuzzy synthetic plush pile, "
    "realistic fur coat, photoreal animal fur, ordinary flesh-and-fur animal, realistic biological mammal, normal wolf, normal fox, normal cat, normal bear, taxidermy"
)

HEALTHY_CREATURE_EXTRA_NEGATIVE = (
    "decorative repair stitching, blanket-stitch outlines, random stitched scars, random patches, patchwork toy body, exposed stuffing, torn toy, broken plush, "
    "wounds, tears, missing exterior tissue, exposed inner fiber"
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
            "a friendly original Guardian companion species with agile living-creature proportions and a head sized naturally for its body, "
            "intact continuous textile integument completely encloses the torso limbs neck and head with no openings into the body, "
            "no damage patches exposed fiber decorative repair stitches bones ribs skull or internal structures are visible, "
            "only a few nearly hidden surface seam-growth lines, clearly defined joints and functional paws feet wings or other locomotor anatomy, "
            "elemental or biome traits integrated as natural organs markings crests leaves crystals or thread structures, "
            "curious active behavior and a readable fantasy-creature silhouette, cute through expression movement and species design rather than baby-doll or stuffed-toy proportions"
        ),
        negative=LIVING_FABRIC_BASE_NEGATIVE + ", " + HEALTHY_CREATURE_EXTRA_NEGATIVE,
    ),
    "guardian_corrupt": CreatureFamilyContract(
        family="guardian_corrupt",
        positive=(
            "a corrupted Guardian that unmistakably retains the functional living body shape and species language of a healthy Guardian, "
            "continuous textile integument fully encloses most of the body and remains the dominant visible surface, damage is localized and meaningful rather than an open anatomical cutaway, "
            "a few torn surface seam wounds may expose pale tangled thread or cotton-like inner fiber only at those small damaged sites, never bones ribs spine skull or a hollow torso, "
            "moss vines fungus or roots may grow through localized wounds, corrupted Thread energy alters color behavior and posture, "
            "the creature remains self-propelled dangerous and externally coherent rather than resembling a skeleton, corpse, broken toy or ordinary diseased animal"
        ),
        negative=LIVING_FABRIC_BASE_NEGATIVE + ", full-body exposed interior, mostly missing integument, skeletal monster",
    ),
    "guardian_boss": CreatureFamilyContract(
        family="guardian_boss",
        positive=(
            "an ancient elite boss-tier Guardian with the same living textile biology, a massive but functionally built nonhuman body and dominant species-specific silhouette, "
            "clear weight distribution and visibly separated locomotor limbs under a fully enclosed continuous exterior body, "
            "continuous textile integument covers the torso and all internal support structures; old repairs and torn seam wounds are localized evidence of age and battle, exposing fibrous inner tissue only at small damaged surface sites, "
            "no bones ribs spine skull or hollow anatomical framework are visible, "
            "relic-like growths biome features and powerful corrupted Thread energy communicate age lore and threat, visually a major living organism rather than a giant toy or undead skeleton"
        ),
        negative=LIVING_FABRIC_BASE_NEGATIVE + (
            ", humanoid, human torso, bodybuilder anatomy, gorilla, ape, muscular biped, furry werewolf, anthropomorphic mascot, open ribcage, skeletal boss"
        ),
    ),
    "enemy_creature": CreatureFamilyContract(
        family="enemy_creature",
        positive=(
            "a wild hostile Plushtopia species from the same living textile ecosystem, feral predatory and wary rather than companion-like, "
            "intact continuous matte woven felted quilted or layered textile integument completely encloses the whole healthy body, with no decorative patchwork repairs exposed filling wounds or openings into the torso, "
            "no bones ribs spine skull or internal structures are visible, sparse thread bristles replace ordinary fur and natural surface seam-growth structures follow the body without outlining toy panels, "
            "low center of gravity articulated joints tense weight-bearing limbs and focused predatory eyes create believable locomotion and threat, "
            "an original dangerous monster silhouette clearly native to Plushtopia rather than a normal animal dressed in fabric, an anatomical model or a cute mascot"
        ),
        negative=LIVING_FABRIC_BASE_NEGATIVE + ", " + HEALTHY_CREATURE_EXTRA_NEGATIVE + (
            ", smiling mascot face, cute mascot, kawaii mascot, friendly pet expression, rounded baby proportions, oversized friendly eyes"
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
