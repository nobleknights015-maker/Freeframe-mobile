"""Reference-derived style steering for Plushbound production.

The profiles describe broad rendering qualities without copying protected designs.
Native creature profiles share a living-fabric ecosystem: the subject must read as
an animated creature first and textile-bodied second.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


STYLE_PROFILE_VERSION = "mt2.0-living-fabric"

COMMON_AVOID = (
    "early-2000s anime-game rendering, retro visual-novel softness, television-anime cel frame, thick uniform black outlines, "
    "flat two-tone cel shading, simple cartoon face shading, hard inked contour around every form, muddy airbrush, watercolor haze, "
    "washed-out color, sepia cast, photorealism, excessive bloom, photographic depth of field, indistinct material rendering, "
    "flat mobile-game vector art, generic stock-fantasy costume, plastic CGI surfaces"
)


@dataclass(frozen=True)
class StyleProfile:
    name: str
    positive: str
    negative: str = COMMON_AVOID

    def apply(self, request: dict) -> dict:
        result = dict(request)
        prompt = str(result.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("prompt must not be empty")
        head, sep, tail = prompt.partition(". ")
        if sep:
            result["prompt"] = f"{head}. {self.positive}. {tail}"
        else:
            result["prompt"] = f"{prompt}. {self.positive}"
        existing_negative = str(result.get("negative_prompt", "")).strip()
        result["negative_prompt"] = ", ".join(
            part for part in (self.negative, existing_negative) if part
        )
        result["render_style_profile"] = self.name
        result["render_style_version"] = STYLE_PROFILE_VERSION
        return result

    def metadata(self) -> dict:
        return {**asdict(self), "version": STYLE_PROFILE_VERSION}


STYLE_PROFILES: dict[str, StyleProfile] = {
    "plushbound_mv": StyleProfile(
        name="plushbound_mv",
        positive=(
            "clean premium contemporary fantasy JRPG illustration, anime-derived anatomy rendered with refined digital painting, "
            "controlled line presence, crisp silhouette, layered directional lighting, sophisticated saturated color grading, "
            "precise material separation, current-generation console-RPG promotional finish"
        ),
    ),
    "plushbound_trinity": StyleProfile(
        name="plushbound_trinity",
        positive=(
            "premium contemporary fantasy JRPG character key-art illustration, refined painted skin planes, crisp grouped hair and costume shapes, "
            "minimal visible contour, layered directional light with colored bounce, sophisticated saturated color grading, "
            "precise differentiation of cloth leather metal and fantasy materials, controlled edge hierarchy, sharp high-detail digital finish, "
            "current-generation console-RPG promotional art"
        ),
    ),
    "plushbound_guardian_2d_candidate": StyleProfile(
        name="plushbound_guardian_2d_candidate",
        positive=(
            "original contemporary 2D fantasy JRPG companion-creature key art of a living fantasy companion species native to Plushtopia, "
            "cute and expressive without chibi deformation, creature anatomy and behavior first and textile body second, coherent weight-bearing animal anatomy and animated creature posture, "
            "soft woven or felt-like textile hide integrated into the living form with restrained seam markings and fiber details, "
            "elemental traits growing naturally from the body, layered directional light with colored bounce, precise material definition, sharp high-detail digital finish, "
            "natural in-world scale and candid creature presence, single creature presentation with no model-sheet layout and no typography"
        ),
        negative=COMMON_AVOID + (
            ", studio product photo, product-photo lighting, photographed toy, retail plush toy, stuffed animal, teddy bear, rag doll, doll, "
            "collectible product render, shelf merchandise, catalog image, plastic figurine, vinyl toy, inert object"
        ),
    ),
    "plushbound_hybrid": StyleProfile(
        name="plushbound_hybrid",
        positive=(
            "original premium contemporary Plushbound fantasy JRPG key art, anime-derived anatomy rendered as polished game illustration rather than cel animation, "
            "minimal visible contour, refined painted face, crisp grouped hair and costume shapes, layered directional light with colored bounce, sophisticated controlled palette, "
            "handcrafted fantasy costume with finely differentiated materials, controlled edge hierarchy, restrained atmosphere, sharp high-detail current-generation 2D console-RPG finish"
        ),
    ),
    "plushbound_trinity_creature": StyleProfile(
        name="plushbound_trinity_creature",
        positive=(
            "premium contemporary fantasy JRPG creature key art of a living Plushtopia species, creature first and textile second, "
            "form-defined predatory anatomy with minimal ink contour and crisp readable silhouette, woven felt quilted or thread-based hide integrated into living anatomy, "
            "seam structures following musculature and fiber tufts behaving like fur or bristles, believable weight locomotion and alert expression, "
            "layered directional light with colored bounce and tight contact shadow, sophisticated controlled color grading, "
            "precise focal edges with softer turning-form edges, one creature as the clear focal subject, natural in-world presentation, "
            "current-generation 2D game-art finish, no poster layout and no typography"
        ),
        negative=COMMON_AVOID + (
            ", ordinary flesh-and-fur animal, realistic mammal, normal wolf, normal cat, normal fox, taxidermy, "
            "retail plush toy, stuffed animal, teddy bear, rag doll, toy product render, shelf merchandise, inert object"
        ),
    ),
    "plushbound_trinity_environment": StyleProfile(
        name="plushbound_trinity_environment",
        positive=(
            "premium contemporary fantasy JRPG environment key art, painterly form definition without heavy cartoon outlines, luminous controlled color grading, crisp architecture and vegetation, "
            "clear foreground middle-ground and distance hierarchy, layered directional light with reflected color and clean atmospheric separation, rich handcrafted world detail and textile motifs integrated naturally into structures, "
            "precise material definition, sharp modern digital finish, traversable path logic, no foreground hero, no poster composition"
        ),
    ),
}


def get_style_profile(name: str) -> StyleProfile:
    try:
        return STYLE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown style profile: {name}") from exc
