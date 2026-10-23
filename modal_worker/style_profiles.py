"""Reference-derived style steering for Plushbound production.

The profiles describe visual qualities from the user's MV and Trinity references
without copying characters, logos, or layouts. They remain separate from V3.2
composition presets so proven anatomy/composition rules stay stable.

SDXL-family encoders have finite token windows. Style language is therefore kept
compact and inserted immediately after the subject sentence: early enough to be
seen, but before the V3.2 framing/anatomy language gets pushed out.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


STYLE_PROFILE_VERSION = "mt1.2"

COMMON_AVOID = (
    "retro visual-novel softness, muddy airbrush, washed-out color, photorealism, excessive bloom"
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
            "clean modern fantasy JRPG key art, crisp anime face and bright eyes, precise linework, "
            "clean hair shapes, cel-painted shading, refined costume materials, restrained highlights"
        ),
    ),
    "plushbound_trinity": StyleProfile(
        name="plushbound_trinity",
        positive=(
            "bright modern fantasy JRPG key art, crisp anime features, vivid controlled colors, "
            "energetic clean lighting, rich costume materials, dimensional cel shading, polished promotional finish"
        ),
    ),
    "plushbound_hybrid": StyleProfile(
        name="plushbound_hybrid",
        positive=(
            "modern fantasy JRPG key art, crisp anime face and linework, vivid controlled colors, "
            "clean hair shapes, cel-painted forms, distinct costume materials, restrained bloom, polished contemporary RPG finish"
        ),
    ),
}


def get_style_profile(name: str) -> StyleProfile:
    try:
        return STYLE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown style profile: {name}") from exc
