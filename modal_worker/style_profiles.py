"""Reference-derived style steering for Plushbound production.

The profiles describe broad visual qualities analyzed from official public MV and
Trinity promotional references without copying characters, logos, costumes, or
layouts. They remain separate from V3.2 composition presets so proven anatomy
and composition rules stay stable.

The language below intentionally describes broad rendering behavior rather than
asking a renderer to reproduce a specific copyrighted work. Original Plushbound
identity and project-owned reference art remain the primary source of subject
identity.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


STYLE_PROFILE_VERSION = "mt1.6"

COMMON_AVOID = (
    "retro visual-novel softness, muddy airbrush, washed-out color, photorealism, "
    "excessive bloom, photographic depth of field, indistinct material rendering, "
    "flat mobile-game vector art, generic stock-fantasy costume, plastic CGI surfaces"
)


@dataclass(frozen=True)
class StyleProfile:
    name: str
    positive: str
    negative: str = COMMON_AVOID

    def apply(self, request: dict) -> dict:
        """Return a copy with compact style tokens inserted after the subject."""
        result = dict(request)
        prompt = str(result.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("request prompt must not be empty")
        existing_negative = str(result.get("negative_prompt", "")).strip()

        head, sep, tail = prompt.partition(". ")
        if sep:
            result["prompt"] = f"{head}. {self.positive}. {tail}"
        else:
            result["prompt"] = f"{prompt}. {self.positive}"
        result["negative_prompt"] = ", ".join(
            part for part in (self.negative, existing_negative) if part
        )
        result["render_style_profile"] = self.name
        result["render_style_version"] = STYLE_PROFILE_VERSION
        return result

    def metadata(self) -> dict:
        return {**asdict(self), "version": STYLE_PROFILE_VERSION}


STYLE_PROFILES = {
    "plushbound_mv": StyleProfile(
        name="plushbound_mv",
        positive=(
            "clean contemporary fantasy JRPG key art, crisp anime facial construction and bright controlled eyes, "
            "deliberate linework with tapered edges, clearly separated hair and costume shapes, firm cel-painted light-shadow groups, "
            "subtle secondary gradients only inside major shadow forms, distinct cloth leather metal and stitched-fabric materials, "
            "readable silhouette at thumbnail size, restrained polished highlights, cover-illustration finish"
        ),
    ),
    "plushbound_trinity": StyleProfile(
        name="plushbound_trinity",
        positive=(
            "high-end modern fantasy JRPG promotional character key art, crisp anime features and expressive eyes, saturated disciplined palette, "
            "layered asymmetrical costume design with clear shape hierarchy, firm cel shading plus selective painterly blending, "
            "distinct cloth leather metal embroidery and stitched-fabric response, warm key light with restrained cool rim light, "
            "precise specular accents instead of glow, strong silhouette separation, polished console-RPG character illustration"
        ),
    ),
    "plushbound_trinity_creature": StyleProfile(
        name="plushbound_trinity_creature",
        positive=(
            "high-end modern fantasy JRPG creature illustration, crisp readable anatomy and silhouette, saturated disciplined palette, "
            "firm cel-painted lighting with selective painterly texture, distinct fur hide wood cloth or magical materials as appropriate, "
            "controlled edge highlights, one creature as the clear focal subject, natural in-world presentation, no poster layout, no typography"
        ),
    ),
    "plushbound_trinity_environment": StyleProfile(
        name="plushbound_trinity_environment",
        positive=(
            "high-end modern fantasy JRPG environment painting, luminous disciplined color, crisp readable architecture and vegetation, "
            "layered foreground middle ground and distance, firm painted light-shadow structure with selective soft atmospheric depth, "
            "rich handcrafted world details and textile motifs integrated naturally into structures, traversable game-world readability, "
            "pure landscape illustration with no foreground hero, no character focal point, no poster composition, no title, no typography, no logo"
        ),
    ),
    "plushbound_guardian_2d_candidate": StyleProfile(
        name="plushbound_guardian_2d_candidate",
        positive=(
            "original 2D fantasy JRPG companion-creature illustration, cute but not chibi-deformed, clean animal silhouette and readable face, "
            "handcrafted sewn-fabric anatomy with subtle seams and soft textile texture, crisp illustrated edges rather than photographed plush fibers, "
            "firm cel-painted light-shadow groups with selective painterly softness, restrained magical accent glow, natural in-world scale, "
            "single creature presentation with no product-photo lighting, no collectible-toy staging, no model-sheet layout and no typography"
        ),
    ),
    "plushbound_hybrid": StyleProfile(
        name="plushbound_hybrid",
        positive=(
            "original Plushbound modern fantasy JRPG cover art, crisp anime face and clean tapered linework, saturated controlled palette, "
            "clear hair and costume shape separation, firm cel-painted forms with selective painterly polish, layered handcrafted fantasy costume, "
            "distinct cloth leather metal embroidery and stitched-fabric materials, warm directional light with restrained rim separation, "
            "readable silhouette, minimal bloom, polished contemporary console-RPG promotional finish"
        ),
    ),
}


def get_style_profile(name: str) -> StyleProfile:
    try:
        return STYLE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown style profile: {name}") from exc
