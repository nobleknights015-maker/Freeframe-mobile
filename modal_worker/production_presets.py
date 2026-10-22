"""Production-oriented generation presets for Plushbound asset benchmarking.

These presets intentionally describe an original cozy fantasy JRPG visual language.
They do not reference or reproduce proprietary RPG Maker characters or artwork.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


BASE_NEGATIVE = (
    "text, watermark, logo, signature, blurry, low detail, low resolution, "
    "malformed anatomy, deformed hands, extra fingers, extra limbs, fused limbs, "
    "duplicate subject, cropped face, distorted face, asymmetrical eyes"
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
            "original polished fantasy JRPG character concept art, Plushbound Legends, "
            "clean expressive anime-inspired illustration, coherent normal anatomy, "
            "clear silhouette, refined costume design, soft dimensional shading"
        ),
        negative_prompt=BASE_NEGATIVE,
        width=768,
        height=1024,
        steps=28,
        guidance_scale=6.0,
    ),
    "plushbound_guardian": ProductionPreset(
        name="plushbound_guardian",
        prompt_prefix=(
            "original Plushbound Legends plush guardian creature concept, premium fantasy JRPG art, "
            "appealing readable silhouette, intentional plush construction, expressive face, "
            "clean anatomy, detailed fabric and magical accents"
        ),
        negative_prompt=BASE_NEGATIVE + ", realistic gore, horror mutation",
        width=768,
        height=768,
        steps=28,
        guidance_scale=6.0,
    ),
    "plushbound_enemy": ProductionPreset(
        name="plushbound_enemy",
        prompt_prefix=(
            "original Plushbound Legends fantasy JRPG enemy concept art, readable battle silhouette, "
            "coherent creature anatomy, polished game illustration, distinctive materials and shapes"
        ),
        negative_prompt=BASE_NEGATIVE,
        width=768,
        height=768,
        steps=28,
        guidance_scale=6.0,
    ),
    "plushbound_environment": ProductionPreset(
        name="plushbound_environment",
        prompt_prefix=(
            "original Plushbound Legends fantasy JRPG environment concept art, inviting storybook world, "
            "strong composition, layered depth, navigable landmarks, polished game key art"
        ),
        negative_prompt=BASE_NEGATIVE + ", character portrait, UI, border",
        width=1024,
        height=768,
        steps=30,
        guidance_scale=6.0,
    ),
}


def get_preset(name: str) -> ProductionPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"unknown production preset: {name}") from exc
