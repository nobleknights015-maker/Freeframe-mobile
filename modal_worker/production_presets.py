"""Production-oriented generation presets for Plushbound assets."""
from __future__ import annotations

from dataclasses import dataclass, asdict

PLUSHBOUND_STYLE_VERSION = "v3.5"
PLUSHBOUND_STYLE = (
    "Plushbound Legends style, warm handcrafted fantasy JRPG world, clean contemporary 2D game illustration, "
    "crisp readable shapes, controlled directional lighting, tactile natural materials, rich disciplined color, sharp digital finish"
)
BASE_NEGATIVE = (
    "text, letters, watermark, logo, signature, UI, frame, border, collage, character sheet, turnaround, multiple views, duplicate subject, "
    "cloned subject, malformed anatomy, extra limbs, fused limbs, deformed hands, extra fingers, cropped face, blurry, low resolution"
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
        prompt = str(prompt).strip()
        if not prompt:
            raise ValueError("prompt must not be empty")
        return {"prompt":f"{prompt}. {self.prompt_prefix}","negative_prompt":self.negative_prompt,"width":self.width,"height":self.height,"steps":self.steps,"guidance_scale":self.guidance_scale,"seed":int(seed),"style_preset":self.name,"style_version":PLUSHBOUND_STYLE_VERSION}
    def metadata(self) -> dict:
        return {**asdict(self), "style_version": PLUSHBOUND_STYLE_VERSION}

PRESETS: dict[str, ProductionPreset] = {
    "plushbound_character": ProductionPreset(
        "plushbound_character",
        f"{PLUSHBOUND_STYLE}. premium contemporary fantasy JRPG character art, one adult humanoid subject only, single candid full-length scene, natural three-quarter standing pose, complete body visible from head to boots, one continuous background, refined face and hands, layered fantasy clothing with readable material separation, clean silhouette, current-generation console-RPG presentation",
        f"{BASE_NEGATIVE}, presentation board, split screen, lineup, pose sheet, turnaround sheet, contact sheet, front side back views, alternate outfit views, duplicated person, childlike proportions",
        768,1024,28,5.0,
    ),
    "plushbound_guardian": ProductionPreset(
        "plushbound_guardian",
        f"{PLUSHBOUND_STYLE}. one living nonhuman Guardian species native to Plushtopia, animated fantasy-creature anatomy and behavior, biological textile dermis with visible woven structure rather than fuzzy toy pile or realistic animal fur, sparse anatomical seam lines, clear functional feet paws wings fins or other locomotor structures, natural creature eyes and readable original silhouette, single creature only, natural in-world presentation",
        f"{BASE_NEGATIVE}, retail plush toy, stuffed animal, teddy bear, rag doll, doll, beanbag toy, store-bought plush, plush merchandise, product photo, studio product lighting, shelf display, catalog product, vinyl figurine, plastic toy, inert object, fuzzy synthetic plush pile, realistic fur coat",
        768,768,28,5.0,
    ),
    "plushbound_enemy": ProductionPreset(
        "plushbound_enemy",
        f"{PLUSHBOUND_STYLE}. one hostile living textile organism native to Plushtopia, low nonhuman battle creature, animal spine parallel to the ground when quadrupedal, clear shoulder hip and limb structure, visibly woven quilted or thread-based biological hide integrated into predatory anatomy, sparse fiber bristles instead of ordinary fur, dangerous readable silhouette, believable weight and locomotion, single creature only, natural in-world battle presentation",
        f"{BASE_NEGATIVE}, humanoid, human torso, biped, upright torso, gorilla, ape, centaur, weapon-wielding person, ordinary flesh-and-fur animal, realistic mammal, normal wolf, normal fox, normal cat, taxidermy, retail plush toy, stuffed animal, teddy bear, rag doll, product photo, shelf display, inert object",
        1024,768,28,5.0,
    ),
    "plushbound_environment": ProductionPreset(
        "plushbound_environment",
        f"{PLUSHBOUND_STYLE}. Outdoor landscape only, no foreground hero, traversable fantasy JRPG environment, clear pathing and depth, coherent foreground middle-ground and background, region-specific vegetation and architecture, readable natural landmarks, current-generation 2D game environment presentation",
        f"{BASE_NEGATIVE}, foreground character, hero portrait, character poster, presentation board, impossible pathing, photoreal landscape, excessive haze",
        1024,768,28,5.0,
    ),
}

def get_preset(name: str) -> ProductionPreset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"unknown production preset: {name}") from exc
