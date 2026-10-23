"""Reference-derived style steering for Plushbound production.

These profiles describe visual qualities observed in the user's RPG Maker MV and
Trinity references without copying characters, logos, or layouts. They are kept
separate from V3.2 composition presets so proven anatomy/composition constraints
remain frozen while rendering style is calibrated independently.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


STYLE_PROFILE_VERSION = "mt1.0"

COMMON_AVOID = (
    "early-2000s visual novel look, retro anime wallpaper, soft airbrushed face, "
    "muddy painterly blending, hazy soft focus, washed-out colors, sepia cast, "
    "plastic skin, photorealistic rendering, excessive bloom, indistinct costume materials"
)


@dataclass(frozen=True)
class StyleProfile:
    name: str
    positive: str
    negative: str = COMMON_AVOID

    def apply(self, request: dict) -> dict:
        """Return a copy of a generation request with deterministic style steering."""
        result = dict(request)
        prompt = str(result.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("request prompt must not be empty")
        existing_negative = str(result.get("negative_prompt", "")).strip()
        result["prompt"] = f"{prompt}. {self.positive}"
        result["negative_prompt"] = ", ".join(
            part for part in (existing_negative, self.negative) if part
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
            "clean polished fantasy JRPG character key art inspired by the visual qualities of RPG Maker MV cover art, "
            "precise anime facial construction, bright expressive eyes, crisp deliberate line definition, "
            "clean separated hair shapes, cel-painted shading with controlled soft gradients, elegant readable silhouette, "
            "refined fabric folds and jewelry details, sharp material boundaries, restrained highlights, "
            "professional promotional illustration finish, contemporary high-resolution rendering"
        ),
    ),
    "plushbound_trinity": StyleProfile(
        name="plushbound_trinity",
        positive=(
            "bright modern fantasy JRPG promotional illustration inspired by the visual qualities of RPG Maker Trinity cover art, "
            "crisp anime features, vivid controlled color palette, energetic but clean lighting, "
            "richly separated cloth leather metal and ornament materials, luminous accent highlights, "
            "strong costume shape language, clean hair clumps, dimensional cel-painted rendering, "
            "colorful contemporary console-and-mobile RPG key-art polish without excessive gloss"
        ),
    ),
    "plushbound_hybrid": StyleProfile(
        name="plushbound_hybrid",
        positive=(
            "modern Plushbound fantasy JRPG promotional key art combining MV-like character readability with Trinity-like color and material polish, "
            "precise attractive anime face, bright detailed eyes, crisp controlled line definition, clean separated hair shapes, "
            "cel-painted forms with subtle smooth gradients, vivid but harmonious fantasy colors, "
            "distinct cloth leather metal lace and jewelry materials, elegant silhouette, confident focal lighting, "
            "sharp readable details, restrained bloom, premium contemporary console-and-mobile RPG illustration finish"
        ),
    ),
}


def get_style_profile(name: str) -> StyleProfile:
    try:
        return STYLE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown style profile: {name}") from exc
