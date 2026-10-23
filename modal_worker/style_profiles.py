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


STYLE_PROFILE_VERSION = "mt1.9"

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
            "premium contemporary fantasy JRPG key-art illustration with anime-derived proportions rather than a television-anime frame, "
            "form-defined rendering with minimal visible contour, finely painted facial planes and controlled detailed eyes, crisp grouped hair masses, "
            "layered light and shadow with colored bounce light, subtle skin translucency, rich disciplined color grading, finely resolved cloth leather metal and stitched-fabric materials, "
            "precise edge hierarchy with hard focal edges and softer turning-form edges, polished current-generation 2D game key-art finish"
        ),
    ),
    "plushbound_trinity": StyleProfile(
        name="plushbound_trinity",
        positive=(
            "premium contemporary fantasy JRPG character key-art illustration, anime-derived anatomy but rendered as polished game illustration rather than cel animation, "
            "form-defined face with refined painted skin planes, detailed luminous eyes, tiny controlled lashes and brows, minimal visible contour except at focal separations, "
            "hair built from crisp grouped masses with selective strand accents, layered directional lighting with colored bounce and tight contact shadow, "
            "sophisticated saturated color grading, cloth leather metal embroidery and stitched-fabric each showing distinct surface response, "
            "controlled edge hierarchy, restrained atmosphere, sharp high-detail digital finish, current-generation console-RPG promotional art"
        ),
    ),
    "plushbound_trinity_creature": StyleProfile(
        name="plushbound_trinity_creature",
        positive=(
            "premium contemporary fantasy JRPG creature key art, form-defined anatomy with minimal ink contour, crisp readable silhouette, "
            "layered directional light with colored bounce and tight contact shadow, sophisticated controlled color grading, finely resolved fur hide wood cloth and magical materials, "
            "precise focal edges with softer turning-form edges, one creature as the clear focal subject, natural in-world presentation, current-generation 2D game-art finish, no poster layout and no typography"
        ),
    ),
    "plushbound_trinity_environment": StyleProfile(
        name="plushbound_trinity_environment",
        positive=(
            "premium contemporary fantasy JRPG environment key art, painterly form definition without heavy cartoon outlines, luminous controlled color grading, crisp architecture and vegetation, "
            "clear foreground middle-ground and distance hierarchy, layered directional light with reflected color and clean atmospheric separation, rich handcrafted world detail and textile motifs integrated naturally into structures, "
            "precise material definition, sharp modern digital finish, traversable game-world readability, pure landscape with no foreground hero, no poster composition, no title, no typography and no logo"
        ),
    ),
    "plushbound_guardian_2d_candidate": StyleProfile(
        name="plushbound_guardian_2d_candidate",
        positive=(
            "original contemporary 2D fantasy JRPG companion-creature key art, cute but not chibi-deformed, form-defined animal anatomy with minimal ink contour, "
            "handcrafted sewn-fabric body with subtle seams and graphic textile texture, layered directional light with colored bounce, precise material definition, sharp high-detail digital finish, "
            "natural in-world scale, single creature presentation with no product-photo lighting, no collectible-toy staging, no model-sheet layout and no typography"
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
}


def get_style_profile(name: str) -> StyleProfile:
    try:
        return STYLE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown style profile: {name}") from exc
