"""Reference-derived style steering for Plushbound production."""
from __future__ import annotations
from dataclasses import asdict, dataclass

STYLE_PROFILE_VERSION = "mt2.0-living-fabric"
COMMON_AVOID = (
    "early-2000s anime-game rendering, retro visual-novel softness, television-anime cel frame, thick uniform black outlines, flat two-tone cel shading, simple cartoon face shading, hard inked contour around every form, muddy airbrush, watercolor haze, washed-out color, sepia cast, photorealism, excessive bloom, photographic depth of field, indistinct material rendering, flat mobile-game vector art, generic stock-fantasy costume, plastic CGI surfaces"
)

@dataclass(frozen=True)
class StyleProfile:
    name: str
    positive: str
    negative: str = COMMON_AVOID
    def apply(self, request: dict) -> dict:
        result=dict(request); prompt=str(result.get("prompt","")).strip()
        if not prompt: raise ValueError("prompt must not be empty")
        head,sep,tail=prompt.partition(". "); result["prompt"]=f"{head}. {self.positive}. {tail}" if sep else f"{prompt}. {self.positive}"
        existing=str(result.get("negative_prompt","")).strip(); result["negative_prompt"] = ", ".join(part for part in (self.negative,existing) if part)
        result["render_style_profile"]=self.name; result["render_style_version"]=STYLE_PROFILE_VERSION; return result
    def metadata(self)->dict: return {**asdict(self),"version":STYLE_PROFILE_VERSION}

STYLE_PROFILES: dict[str, StyleProfile] = {
    "plushbound_mv": StyleProfile("plushbound_mv","clean premium contemporary fantasy JRPG illustration, anime-derived anatomy rendered with refined digital painting, controlled line presence, crisp silhouette, layered directional lighting, sophisticated saturated color grading, precise material separation, current-generation console-RPG promotional finish"),
    "plushbound_trinity": StyleProfile("plushbound_trinity","premium contemporary fantasy JRPG character key-art illustration, refined painted skin planes, crisp grouped hair and costume shapes, minimal visible contour, layered directional light with colored bounce, sophisticated saturated color grading, precise differentiation of cloth leather metal and fantasy materials, controlled edge hierarchy, sharp high-detail digital finish, current-generation console-RPG promotional art"),
    "plushbound_guardian_2d_candidate": StyleProfile(
        "plushbound_guardian_2d_candidate",
        "original contemporary 2D fantasy JRPG Guardian-creature key art, unmistakably alive and behaving as a fantasy species, coherent nonhuman anatomy with believable weight and motion, matte woven textile dermis visibly integrated into living form rather than fuzzy fur or a manufactured plush shell, restrained anatomy-following seams, natural creature eyes, elemental traits integrated as biology, layered directional light with colored bounce, precise material definition, sharp high-detail digital finish, natural in-world scale, one creature with no model-sheet layout and no typography",
        COMMON_AVOID + ", studio product photo, product-photo lighting, photographed toy, retail plush toy, stuffed animal, teddy bear, rag doll, doll, collectible product render, shelf merchandise, catalog image, plastic figurine, vinyl toy, inert object, fuzzy synthetic plush pile, realistic fur coat",
    ),
    "plushbound_hybrid": StyleProfile("plushbound_hybrid","original premium contemporary Plushbound fantasy JRPG key art, anime-derived anatomy rendered as polished game illustration rather than cel animation, minimal visible contour, refined painted face, crisp grouped hair and costume shapes, layered directional light with colored bounce, sophisticated controlled palette, handcrafted fantasy costume with finely differentiated materials, controlled edge hierarchy, restrained atmosphere, sharp high-detail current-generation 2D console-RPG finish"),
    "plushbound_trinity_creature": StyleProfile(
        "plushbound_trinity_creature",
        "premium contemporary fantasy JRPG creature key art of a living Plushtopia species, creature first and textile biology second, form-defined predatory anatomy with minimal ink contour and crisp readable silhouette, visibly woven quilted or layered textile dermis integrated across the living body, sparse thread bristles instead of ordinary fur, believable weight locomotion and alert expression, layered directional light with colored bounce and tight contact shadow, sophisticated controlled color grading, precise focal edges with softer turning-form edges, one creature as the clear focal subject, natural in-world presentation, current-generation 2D game-art finish, no poster layout and no typography",
        COMMON_AVOID + ", ordinary flesh-and-fur animal, realistic mammal, normal wolf, normal cat, normal fox, taxidermy, retail plush toy, stuffed animal, teddy bear, rag doll, toy product render, shelf merchandise, inert object, realistic fur coat",
    ),
    "plushbound_trinity_environment": StyleProfile("plushbound_trinity_environment","premium contemporary fantasy JRPG environment key art, painterly form definition without heavy cartoon outlines, luminous controlled color grading, crisp architecture and vegetation, clear foreground middle-ground and distance hierarchy, layered directional light with reflected color and clean atmospheric separation, rich handcrafted world detail and textile motifs integrated naturally into structures, precise material definition, sharp modern digital finish, traversable path logic, no foreground hero, no poster composition"),
}

def get_style_profile(name: str) -> StyleProfile:
    try: return STYLE_PROFILES[name]
    except KeyError as exc: raise ValueError(f"unknown style profile: {name}") from exc
