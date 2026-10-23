"""Reference-derived style steering for Plushbound production.

The profiles describe broad visual qualities analyzed from official public MV and
Trinity promotional references without copying characters, logos, costumes, or
layouts. They remain separate from composition presets so proven anatomy and
composition rules stay stable.

The language below intentionally describes broad rendering behavior rather than
asking a renderer to reproduce a specific copyrighted work. Original Plushbound
identity and project-owned reference art remain the primary source of subject
identity.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


STYLE_PROFILE_VERSION = "mt1.8"

COMMON_AVOID = (
    "early-2000s anime-game rendering, retro visual-novel softness, thick uniform black outlines, flat two-tone cel shading, "
    "muddy airbrush, watercolor haze, washed-out color, sepia cast, photorealism, excessive bloom, photographic depth of field, "
    "indistinct material rendering, flat mobile-game vector art, generic stock-fantasy costume, plastic CGI surfaces"
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
            "contemporary premium fantasy JRPG key art, modern anime facial construction with detailed controlled eyes, "
            "fine colored linework with selective line suppression on lit planes, crisp hair-clump design, strong graphic shape hierarchy, "
            "layered cel shading with secondary reflected light and subtle skin-tone transitions, rich controlled color grading, "
            "finely resolved cloth leather metal and stitched-fabric materials, precise edge control, restrained atmosphere, polished current-generation 2D finish"
        ),
    ),
    "plushbound_trinity": StyleProfile(
        name="plushbound_trinity",
        positive=(
            "contemporary high-budget fantasy JRPG promotional character art, refined modern anime face with detailed eyes and natural skin-tone transitions, "
            "fine colored contour lines rather than heavy black outlines, selective line disappearance on brightly lit edges, crisp layered hair shapes, "
            "sophisticated saturated color grading, layered graphic cel shadows with secondary bounce light and tight ambient occlusion, "
            "finely differentiated cloth leather metal embroidery and stitched-fabric materials, precise specular accents without glow haze, "
            "clean cinematic separation, high-detail sharp digital finish, current-generation console-RPG 2D illustration"
        ),
    ),
    "plushbound_trinity_creature": StyleProfile(
        name="plushbound_trinity_creature",
        positive=(
            "contemporary high-budget fantasy JRPG creature illustration, crisp readable anatomy and silhouette, fine colored edge work instead of heavy black contour, "
            "layered graphic light-shadow shapes with secondary bounce light, sophisticated controlled color grading, finely resolved fur hide wood cloth and magical materials, "
            "tight contact shadows and precise highlights without haze, one creature as the clear focal subject, natural in-world presentation, "
            "high-detail current-generation 2D game-art finish, no poster layout and no typography"
        ),
    ),
    "plushbound_trinity_environment": StyleProfile(
        name="plushbound_trinity_environment",
        positive=(
            "contemporary high-budget fantasy JRPG environment illustration, luminous controlled color grading, crisp architecture and vegetation with fine selective linework, "
            "clear foreground middle-ground and distance hierarchy, layered graphic light-shadow structure with reflected light and clean atmospheric separation, "
            "rich handcrafted world detail and textile motifs integrated naturally into structures, precise material definition, sharp modern digital finish, "
            "traversable game-world readability, pure landscape illustration with no foreground hero, no character focal point, no poster composition, no title, no typography and no logo"
        ),
    ),
    "plushbound_guardian_2d_candidate": StyleProfile(
        name="plushbound_guardian_2d_candidate",
        positive=(
            "original contemporary 2D fantasy JRPG companion-creature illustration, cute but not chibi-deformed, clean animal silhouette and readable face, "
            "fine colored illustrated edges instead of thick black contour, handcrafted sewn-fabric anatomy with subtle seams and graphic textile texture, "
            "layered clean light-shadow shapes with secondary bounce light, restrained magical accents, precise material definition, sharp high-detail digital finish, "
            "natural in-world scale, single creature presentation with no product-photo lighting, no collectible-toy staging, no model-sheet layout and no typography"
        ),
    ),
    "plushbound_hybrid": StyleProfile(
        name="plushbound_hybrid",
        positive=(
            "original contemporary Plushbound fantasy JRPG key art, refined modern anime face, fine colored tapered linework and selective line suppression, "
            "crisp hair and costume shape separation, layered graphic shadows with secondary reflected light, sophisticated controlled palette, "
            "layered handcrafted fantasy costume with finely differentiated materials, precise highlights without bloom haze, clean cinematic separation, "
            "strong silhouette readability, high-detail current-generation 2D console-RPG finish"
        ),
    ),
}


def get_style_profile(name: str) -> StyleProfile:
    try:
        return STYLE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown style profile: {name}") from exc
