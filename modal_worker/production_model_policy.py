"""Fail-closed production renderer routing for Plushbound image jobs.

This module selects the bounded-production renderer without authorizing catalog-wide
production. It is deliberately separate from Atlas personality and from visual art
direction: it only declares which worker/model is allowed to execute a request and
adds renderer-specific compliance language needed for reliable Klein output.
"""
from __future__ import annotations

try:
    from .model_catalog import apply_model_defaults, get_production_renderer
except ImportError:
    from model_catalog import apply_model_defaults, get_production_renderer

PRODUCTION_MODEL_POLICY_VERSION = "production-model-policy-v4-klein-creature-anatomy"
PRODUCTION_RENDERER_ROUTE = "flux2_klein"
SUPPORTED_PRESETS = frozenset({
    "plushbound_character",
    "plushbound_guardian",
    "plushbound_enemy",
    "plushbound_environment",
})

_KLEIN_COMPLIANCE = {
    "plushbound_character": (
        "Klein production constraint: render one character only in one continuous in-world scene. "
        "All garment and accessory surfaces are plain, clean, unlettered and unmarked; cloth panels are solid woven material "
        "with restrained construction seams only where pieces join. The visible lower edge of every tunic, mantle, sleeve and trouser cuff "
        "is a smooth uninterrupted plain fabric edge with zero decorative stitching, cross-stitching, border marks, embroidery, trim, "
        "glyph-like shapes, name tapes, badges, insignia, symbols, logos, numbers or writing. Leave the lower tunic hem visually blank."
    ),
    "plushbound_guardian": (
        "Klein production constraint: render one living Guardian only, behaving as a real fantasy species in its natural habitat. "
        "Its complete exterior is hairless and pile-free: matte woven canvas-like biological skin with visibly interlaced warp-and-weft fibers "
        "following the body form, never a coat of fur, fuzz, velvet, fleece or plush pile. Use proportionate small-to-medium natural creature eyes "
        "set into the skull, not oversized glossy mascot eyes. The face must read as living animal anatomy rather than a toy: no button nose, doll face, "
        "stitched smile or merchandise proportions. Surface variation is simple organic color blocking and sparse anatomy-following seam structure only, "
        "with no letter-like, rune-like, logo-like or printed markings."
    ),
    "plushbound_enemy": (
        "Klein production constraint: render one hostile living-textile creature only, grounded in its natural habitat with believable predatory weight. "
        "The full exterior is hairless and pile-free matte woven textile hide with clearly visible warp-and-weft structure and quilted anatomical planes, "
        "never ordinary fur, fuzz, fleece or a realistic mammal coat. Use an original non-feline, non-canine head silhouette with no cat ears, dog ears, whiskers, "
        "feline muzzle or ordinary wolf/fox/cat facial anatomy. Keep the torso long and low with a clearly horizontal spine, four separated weight-bearing legs, "
        "distinct shoulder and hip structure and four visible ground-contact feet. Eyes are proportionate natural predator eyes, not mascot eyes. Surface variation is "
        "non-symbolic biological textile structure only, with no letter-like, rune-like, logo-like or printed markings."
    ),
    "plushbound_environment": (
        "Klein production constraint: render one continuous traversable landscape without a foreground hero. Any architecture, banners "
        "or cloth decoration uses plain material or simple non-symbolic geometry only; omit signs, lettering, runes, logos and pseudo-text."
    ),
}


def apply_production_model_policy(preset_name: str, request: dict) -> dict:
    preset_name = str(preset_name).strip()
    if preset_name not in SUPPORTED_PRESETS:
        raise ValueError(f"preset is not routed through the bounded production renderer: {preset_name}")

    candidate = get_production_renderer()
    result = apply_model_defaults(request, candidate)
    width = int(result.get("width", 0))
    height = int(result.get("height", 0))
    if width % 16 or height % 16:
        raise ValueError("FLUX.2 Klein production dimensions must be divisible by 16")
    if width > candidate.max_test_resolution or height > candidate.max_test_resolution:
        raise ValueError("bounded production request exceeds the promoted renderer resolution limit")

    prompt = str(result.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("production request prompt must not be empty")
    result["prompt"] = f"{prompt}. {_KLEIN_COMPLIANCE[preset_name]}"
    result["renderer_route"] = PRODUCTION_RENDERER_ROUTE
    result["renderer_class"] = "FreeFrameProductionGenerator"
    result["production_model_policy_version"] = PRODUCTION_MODEL_POLICY_VERSION
    result["renderer_compliance_profile"] = f"{preset_name}-klein-v4"
    result["bounded_production_authorized"] = True
    result["automatic_full_production_authorized"] = False
    result["catalog_wide_launch_authorized"] = False
    return result
