"""Production render-style policy for Plushbound master generation.

Only category profiles that have passed bounded workflow validation are routed here.
Creature semantic correctness is additionally enforced by creature_world_policy.
"""
from __future__ import annotations

from typing import Any

from modal_worker.style_profiles import STYLE_PROFILE_VERSION, get_style_profile


PRODUCTION_STYLE_POLICY_VERSION = "style-policy-v5-living-fabric"

VALIDATED_STYLE_BY_PRESET: dict[str, str] = {
    "plushbound_character": "plushbound_trinity",
    "plushbound_guardian": "plushbound_guardian_2d_candidate",
    "plushbound_enemy": "plushbound_trinity_creature",
    "plushbound_environment": "plushbound_trinity_environment",
}


def style_for_preset(preset_name: str) -> str | None:
    return VALIDATED_STYLE_BY_PRESET.get(preset_name)


def apply_production_style(preset_name: str, request: dict[str, Any]) -> dict[str, Any]:
    """Apply the category-appropriate style profile and record the policy decision."""
    result = dict(request)
    style_name = style_for_preset(preset_name)
    if style_name is not None:
        result = get_style_profile(style_name).apply(result)
        result["production_style_validated"] = True
    else:
        result["production_style_validated"] = False
    result["production_style_profile"] = style_name
    result["production_style_policy_version"] = PRODUCTION_STYLE_POLICY_VERSION
    result["production_style_profile_version"] = STYLE_PROFILE_VERSION
    return result
