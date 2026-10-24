"""Fail-closed production renderer routing for Plushbound image jobs.

This module selects the bounded-production renderer without authorizing catalog-wide
production. It is deliberately separate from Atlas personality and from visual art
direction: it only declares which worker/model is allowed to execute a request.
"""
from __future__ import annotations

try:
    from .model_catalog import apply_model_defaults, get_production_renderer
except ImportError:
    from model_catalog import apply_model_defaults, get_production_renderer

PRODUCTION_MODEL_POLICY_VERSION = "production-model-policy-v1-klein-bounded"
PRODUCTION_RENDERER_ROUTE = "flux2_klein"
SUPPORTED_PRESETS = frozenset({
    "plushbound_character",
    "plushbound_guardian",
    "plushbound_enemy",
    "plushbound_environment",
})


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

    result["renderer_route"] = PRODUCTION_RENDERER_ROUTE
    result["renderer_class"] = "FreeFrameProductionGenerator"
    result["production_model_policy_version"] = PRODUCTION_MODEL_POLICY_VERSION
    result["bounded_production_authorized"] = True
    result["automatic_full_production_authorized"] = False
    result["catalog_wide_launch_authorized"] = False
    return result
