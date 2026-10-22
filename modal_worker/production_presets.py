"""Production-oriented generation presets for Plushbound asset benchmarking.

Prompt architecture deliberately puts the requested asset first. SDXL follows
short subject/composition instructions more reliably than a long shared style
preamble; Plushbound art direction is appended as a compact finishing language.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


PLUSHBOUND_STYLE_VERSION = "v3.1"
PLUSHBOUND_STYLE = (
    "Plushbound Legends style, warm handcrafted fantasy JRPG, painterly anime-inspired game art, "
    "clean shapes, soft dimensional light, tactile natural materials, harmonious colors"
)

BASE_NEGATIVE = (
    "text, letters, watermark, logo, signature, UI, frame, border, collage, character sheet, turnaround, "
    "multiple views, duplicate subject, cloned subject, malformed anatomy, extra limbs, fused limbs, "
    "deformed hands, extra fingers, cropped face, blurry, low resolution"
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
            "prompt": f"{prompt}. {self.prompt_prefix}",
            "negative_prompt": self.negative_prompt,
            "width": self.width,
            "height": self.height,
            "steps": self.steps,
            "guidance_scale": self.guidance_scale,
            "seed": seed,
            "style_preset": self.name,
            "style_version": PLUSHBOUND_STYLE_VERSION,
        }

    def metadata(self) -> dict:
        return {**asdict(self), "style_version": PLUSHBOUND_STYLE_VERSION}


PRESETS = {
    "plushbound_character": ProductionPreset(
        name="plushbound_character",
        prompt_prefix=(
            "SINGLE SUBJECT PORTRAIT: exactly one adult human, exactly one body, exactly one face, one pose, "
            "full body head to toe, centered alone in the image, natural adult proportions, neutral standing pose, "
            "normal anatomy, practical layered fantasy clothing, plain simple background, no alternate views. " + PLUSHBOUND_STYLE
        ),
        negative_prompt=BASE_NEGATIVE + ", child, chibi, mascot proportions, crowd, second person, two people, three people, group, twins, duplicate person, repeated person, lineup, contact sheet, design sheet, reference sheet, alternate outfit, alternate pose, companion creature",
        width=768,
        height=1024,
        steps=28,
        guidance_scale=6.0,
    ),
    "plushbound_guardian": ProductionPreset(
        name="plushbound_guardian",
        prompt_prefix=(
            "One creature only, one pose only, full creature visible, centered, coherent animal anatomy, "
            "clearly sewn plush body with subtle seams and magical accent, simple background. " + PLUSHBOUND_STYLE
        ),
        negative_prompt=BASE_NEGATIVE + ", second creature, multiple creatures, lineup, model sheet, litter, pack, gore, mutation",
        width=768,
        height=768,
        steps=28,
        guidance_scale=6.0,
    ),
    "plushbound_enemy": ProductionPreset(
        name="plushbound_enemy",
        prompt_prefix=(
            "SINGLE NON-HUMANOID MONSTER: exactly one hostile quadrupedal creature, four-legged animal body plan, "
            "moves on four legs, no human torso, no human hands, no clothing, no carried weapon, one pose only, "
            "full creature visible, centered, readable battle silhouette, coherent creature anatomy, simple background. " + PLUSHBOUND_STYLE
        ),
        negative_prompt=BASE_NEGATIVE + ", human, humanoid, biped, standing person, warrior, adventurer, clothing, armor suit, axe, sword, spear, staff, carried weapon, human hands, cute party, second monster, monster group, swarm, lineup, model sheet",
        width=768,
        height=768,
        steps=28,
        guidance_scale=6.0,
    ),
    "plushbound_environment": ProductionPreset(
        name="plushbound_environment",
        prompt_prefix=(
            "Outdoor landscape only, wide establishing view, no foreground character, clear traversable path, "
            "foreground middle ground and distant landmark, coherent vegetation and architecture. " + PLUSHBOUND_STYLE
        ),
        negative_prompt=BASE_NEGATIVE + ", indoor room, interior, tent interior, bedroom, character portrait, foreground hero, poster",
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
