"""Reference-derived style steering for Plushbound production.

The profiles describe broad visual qualities analyzed from official public MV and
Trinity promotional references without copying characters, logos, costumes, or
layouts. They remain separate from V3.2 composition presets so proven anatomy
and composition rules stay stable.

SDXL-family encoders have finite token windows. Style language is therefore kept
compact and inserted immediately after the subject sentence: early enough to be
seen, but before the V3.2 framing/anatomy language gets pushed out.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


STYLE_PROFILE_VERSION = "mt1.3"

COMMON_AVOID = (
    "retro visual-novel softness, muddy airbrush, washed-out color, photorealism, "
    "excessive bloom, photographic depth of field, indistinct material rendering"
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
            "deliberate linework, clearly separated hair and costume shapes, cel-painted light-shadow groups, "
            "distinct cloth leather and metal materials, strong readable silhouette, restrained polished highlights"
        ),
    ),
    "plushbound_trinity": StyleProfile(
        name="plushbound_trinity",
        positive=(
            "polished modern fantasy JRPG promotional illustration, crisp anime features, saturated disciplined colors, "
            "confident layered costume shapes, firm cel-painted shading, selective material highlights, energetic clean lighting, "
            "strong silhouette hierarchy, contemporary game key-art finish"
        ),
    ),
    "plushbound_hybrid": StyleProfile(
        name="plushbound_hybrid",
        positive=(
            "original Plushbound modern fantasy JRPG key art, crisp anime face and clean linework, saturated controlled palette, "
            "clear hair and costume shape separation, cel-painted forms with selective painterly polish, distinct cloth leather metal "
            "and stitched-fabric materials, readable silhouette, restrained bloom, polished contemporary RPG cover-art finish"
        ),
    ),
}


def get_style_profile(name: str) -> StyleProfile:
    try:
        return STYLE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown style profile: {name}") from exc
