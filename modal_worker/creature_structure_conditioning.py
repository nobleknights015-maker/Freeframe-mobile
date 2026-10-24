"""Generator-owned structural conditioning for living Plushbound creatures.

This module is deliberately outside Atlas. Atlas supplies a semantic asset brief;
FreeFrame's production renderer decides when a creature needs project-owned render
style and exterior body-plan references so FLUX.2 Klein does not collapse into fuzzy
mascot mammals. No third-party creature art is used here.
"""
from __future__ import annotations

from dataclasses import dataclass

try:
    from .creature_pose_guides import POSE_GUIDE_VERSION, build_pose_guide
    from .plushbound_style_anchors import STYLE_ANCHOR_LIBRARY_VERSION, get_style_anchor
except ImportError:
    from creature_pose_guides import POSE_GUIDE_VERSION, build_pose_guide
    from plushbound_style_anchors import STYLE_ANCHOR_LIBRARY_VERSION, get_style_anchor

CREATURE_STRUCTURE_CONDITIONING_VERSION = "creature-structure-conditioning-v2-family-anchor"
SUPPORTED_FAMILIES = frozenset({
    "guardian_friendly",
    "guardian_corrupt",
    "guardian_boss",
    "enemy_creature",
})

CONTROL_PROMPT = (
    "Two project-owned reference images are supplied with separate responsibilities. "
    "Reference image 1 is a validated Plushbound creature-family reference: use its polished colorful 2D fantasy JRPG rendering language, "
    "outline treatment, painterly shading, living-textile material language, lighting and color discipline as family-level guidance only. "
    "Do not copy its exact identity, markings or silhouette unless independently required by the written brief. "
    "Reference image 2 is a plain black exterior silhouette: obey only its broad outside body shape, orientation and visible limb count; "
    "ignore its graphic style and do not render it as a shadow. "
    "Create one self-propelled living fantasy organism in a natural habitat. Its body is solid and fully enclosed. "
    "Living textile material is biological integument with visible woven fiber structure conforming to joints and mass, not fur, plush pile, "
    "stuffing, patchwork toy panels or retail merchandise. Eyes are proportionate living eyes, not oversized glossy doll eyes. "
    "No collars, tags, pet accessories, catalog layout, labels or typography."
)


@dataclass(frozen=True)
class CreatureConditioning:
    family: str
    pose_variant: str
    style_anchor_id: str
    style_anchor_sha256: str
    style_anchor_git_blob_sha1: str
    style_anchor_ownership: str
    pose_guide_version: str
    conditioning_version: str = CREATURE_STRUCTURE_CONDITIONING_VERSION

    def metadata(self) -> dict:
        return {
            "conditioning_version": self.conditioning_version,
            "family": self.family,
            "pose_variant": self.pose_variant,
            "pose_guide_version": self.pose_guide_version,
            "style_anchor_library_version": STYLE_ANCHOR_LIBRARY_VERSION,
            "style_anchor_id": self.style_anchor_id,
            "style_anchor_sha256": self.style_anchor_sha256,
            "style_anchor_git_blob_sha1": self.style_anchor_git_blob_sha1,
            "style_anchor_ownership": self.style_anchor_ownership,
            "reference_roles": ["creature_family_render_material_style", "exterior_body_plan_only"],
        }


def infer_pose_variant(family: str, prompt: str) -> str:
    family = str(family).strip()
    text = str(prompt).lower()
    if family not in SUPPORTED_FAMILIES:
        raise ValueError(f"unsupported creature conditioning family: {family}")

    six_legged = any(token in text for token in ("six-legged", "six legged", "six weight-bearing legs", "exactly six"))
    if family == "guardian_boss":
        return "hexapod"
    if family == "guardian_corrupt":
        return "low_quadruped"
    if family == "enemy_creature":
        return "hexapod" if six_legged or "hexapod" in text else "quadruped"

    if any(token in text for token in ("winged", "wings", "flying", "flight")):
        return "winged"
    if any(token in text for token in ("biped", "two-legged", "two legged", "upright")):
        return "biped"
    if any(token in text for token in ("long low", "long-low", "serpentine quadruped")):
        return "long_low"
    return "quadruped"


def build_conditioning(family: str, prompt: str, *, size: int = 512):
    """Return family style image, pose image, control prompt and immutable provenance."""
    family = str(family).strip()
    pose_variant = infer_pose_variant(family, prompt)
    anchor = get_style_anchor(family)
    style_image = anchor.load_image()
    pose_image = build_pose_guide(family, size=size, variant=pose_variant)
    metadata = CreatureConditioning(
        family=family,
        pose_variant=pose_variant,
        style_anchor_id=anchor.anchor_id,
        style_anchor_sha256=anchor.sha256(),
        style_anchor_git_blob_sha1=anchor.git_blob_sha1,
        style_anchor_ownership=anchor.ownership,
        pose_guide_version=POSE_GUIDE_VERSION,
    )
    return style_image, pose_image, CONTROL_PROMPT, metadata
