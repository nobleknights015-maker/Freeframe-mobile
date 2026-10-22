"""Production-oriented generation presets for Plushbound asset benchmarking.

These presets define an original Plushbound Legends visual language. They are
written to keep category outputs visually related while avoiding references to
or reproduction of proprietary RPG Maker characters or artwork.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


# Shared art-direction spine used by every production category. Category prompts
# add function-specific composition rules without changing the world's identity.
PLUSHBOUND_STYLE = (
    "original Plushbound Legends game art, warm handcrafted fantasy JRPG visual language, "
    "painterly anime-inspired rendering, clean confident shapes, soft dimensional lighting, "
    "restrained harmonious color palette, tactile cloth leather wood and stitched-fabric details, "
    "whimsical but grounded design, professional production concept art, no typography"
)

BASE_NEGATIVE = (
    "text, letters, words, caption, subtitle, watermark, logo, signature, artist mark, UI, frame, border, "
    "blurry, low detail, low resolution, jpeg artifacts, oversaturated neon colors, harsh bloom, "
    "malformed anatomy, deformed hands, extra fingers, missing fingers, extra limbs, fused limbs, "
    "duplicate subject, cloned subject, repeated character, multiple views, character sheet, turnaround, "
    "split composition, collage, cropped face, cropped feet, distorted face, asymmetrical eyes"
)


@dataclass(frozen=True)
class ProductionPreset:
    name: str
    prompt_prefix: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    guidance_scale: float

    def apply(self, prompt: str, *, seed: int) -> dict:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("prompt must not be empty")
        return {
            "prompt": f"{self.prompt_prefix}, {prompt}",
            "negative_prompt": self.negative_prompt,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "guidance_scale": self.guidance_scale,
            "seed": seed,
            "style_preset": self.name,
        }

    def metadata(self) -> dict:
        return asdict(self)


PRESETS = {
    "plushbound_character": ProductionPreset(
        name="plushbound_character",
        prompt_prefix=(
            PLUSHBOUND_STYLE + ", single adult character only, one person, full body head-to-toe, "
            "centered three-quarter standing pose, coherent normal anatomy, natural hands, five fingers, "
            "clear readable silhouette, practical layered fantasy clothing, refined costume design, "
            "simple unobtrusive background, game character concept"
        ),
        negative_prompt=BASE_NEGATIVE + ", child proportions, chibi proportions, crowd, companion creature",
        width=768,
        height=1024,
        steps=30,
        guidance_scale=6.0,
    ),
    "plushbound_guardian": ProductionPreset(
        name="plushbound_guardian",
        prompt_prefix=(
            PLUSHBOUND_STYLE + ", exactly one Plush Guardian creature, single creature only, centered full body, "
            "appealing readable silhouette, intentional sewn plush construction, visible seams used sparingly, "
            "expressive face, coherent four-limbed creature anatomy when applicable, detailed fabric and magical accents, "
            "simple unobtrusive ground plane, collectible companion game concept"
        ),
        negative_prompt=BASE_NEGATIVE + ", second creature, litter, pack, realistic gore, horror mutation, taxidermy",
        width=768,
        height=768,
        steps=30,
        guidance_scale=6.0,
    ),
    "plushbound_enemy": ProductionPreset(
        name="plushbound_enemy",
        prompt_prefix=(
            PLUSHBOUND_STYLE + ", exactly one fantasy JRPG enemy, single creature only, centered full body, "
            "readable battle silhouette, coherent creature anatomy, distinctive material language and shapes, "
            "clear gameplay-scale design, simple unobtrusive background, production monster concept"
        ),
        negative_prompt=BASE_NEGATIVE + ", second monster, monster group, swarm, gore, dismemberment",
        width=768,
        height=768,
        steps=30,
        guidance_scale=6.0,
    ),
    "plushbound_environment": ProductionPreset(
        name="plushbound_environment",
        prompt_prefix=(
            PLUSHBOUND_STYLE + ", wide fantasy JRPG environment establishing shot, no foreground character, "
            "clear traversable route from foreground into middle distance, layered depth, readable landmarks, "
            "coherent architecture and vegetation, gameplay-friendly spatial hierarchy, inviting storybook world, "
            "environment concept art rather than poster art"
        ),
        negative_prompt=BASE_NEGATIVE + ", character portrait, foreground hero, giant face, poster composition, floating text",
        width=1024,
        height=768,
        steps=32,
        guidance_scale=6.0,
    ),
}


def get_preset(name: str) -> ProductionPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"unknown production preset: {name}") from exc
