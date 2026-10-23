"""Production-oriented generation presets for Plushbound assets.

V3.2 keeps the proven Plushbound style while separating subject generation from
asset-format language. Character and beast prompts use photographic composition
terms rather than concept-art/model-sheet vocabulary that SDXL can over-interpret.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


PLUSHBOUND_STYLE_VERSION = "v3.2"
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
            "A single candid full-length scene containing one adult traveler standing naturally on a quiet dirt path, "
            "camera at eye level, entire person visible from head through both boots, open empty space around the person, "
            "one continuous background, natural adult anatomy and proportions, practical layered fantasy travel clothing. "
            + PLUSHBOUND_STYLE
        ),
        negative_prompt=BASE_NEGATIVE + ", studio sheet, presentation board, reference board, panels, split screen, triptych, diptych, thumbnails, inset image, repeated figure, second figure, crowd, child, chibi, mannequin, companion creature",
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
            "A single wild four-legged beast prowling horizontally across a forest clearing, animal spine parallel to the ground, "
            "front paws and rear paws supporting the body, long animal torso between shoulder and hips, head projecting forward from the shoulders, "
            "natural quadruped locomotion like a wolf or large cat, creature body filling most of the frame, one continuous forest background. "
            + PLUSHBOUND_STYLE
        ),
        negative_prompt=BASE_NEGATIVE + ", gorilla, ape, monkey, bear standing upright, human, humanoid, biped, upright torso, standing on two legs, human shoulders, human hands, warrior, adventurer, clothing, armor suit, axe, sword, spear, staff, carried weapon, second monster, group, swarm, lineup, model sheet",
        width=896,
        height=640,
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
