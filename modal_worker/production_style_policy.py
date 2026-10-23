"""Production render-style policy for Plushbound master generation.

Only styles that have passed bounded GPU comparison are enabled here. The policy
is deliberately conservative: each preset must earn its production style through
its own same-seed comparison. Guardian remains unstyled because its bounded test
still produced multi-view/model-sheet compositions and unwanted morphology.
"""
from __future__ import annotations

from typing import Any

from style_profiles import STYLE_PROFILE_VERSION, get_style_profile


PRODUCTION_STYLE_POLICY_VERSION = "style-policy-v2"

# Validated by bounded same-seed GPU comparisons.
VALIDATED_STYLE_BY_PRESET: dict[str, str] = {
    "plushbound_character": "plushbound_trinity",
    "plushbound_enemy": "plushbound_trinity",
    "plushbound_environment": "plushbound_trinity",
}


def style_for_preset(preset_name: str) -> str | None:
    return VALIDATED_STYLE_BY_PRESET.get(preset_name)


def apply_production_style(preset_name: str, request: dict[str, Any]) -> dict[str, Any]:
    """Apply only a GPU-validated style profile and record the policy decision."""
    result = dict(request)
    style_name = style_for_preset(preset_name)
    if style_name is not None:
        result = get_style_profile(style_name).apply(result)
        result["production_style_validated"] = True
    else:
        result["production_style_validated"] = False

    result["production_style_policy_version"] = PRODUCTION_STYLE_POLICY_VERSION
    result["production_style_profile"] = style_name
    if style_name is not None:
        result["production_style_profile_version"] = STYLE_PROFILE_VERSION
    return result
