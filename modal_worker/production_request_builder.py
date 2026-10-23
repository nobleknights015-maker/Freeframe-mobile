"""Single authority for building Plushbound production generation requests.

The builder composes the preset, layout repair, render style, living-fabric creature
contract, and optional approved visual reference. Mini-Jarvis and batch launchers
use this same function so planning and rendering cannot silently disagree.
"""
from __future__ import annotations

import re

try:
    from .creature_world_policy import apply_creature_world_policy
    from .guardian_composition_policy import apply_guardian_composition
    from .production_presets import get_preset
    from .production_style_policy import apply_production_style
except ImportError:  # direct-module compatibility for local CI/tests
    from creature_world_policy import apply_creature_world_policy
    from guardian_composition_policy import apply_guardian_composition
    from production_presets import get_preset
    from production_style_policy import apply_production_style

PRODUCTION_REQUEST_BUILDER_VERSION = "production-request-v3-living-fabric"
_REFERENCE_ID_RE = re.compile(r"^[0-9a-f]{64}$")


def build_production_request(
    preset_name: str,
    prompt: str,
    *,
    seed: int,
    reference_id: str | None = None,
    reference_scale: float = 0.35,
    creature_family: str | None = None,
) -> dict:
    request = get_preset(preset_name).apply(prompt, seed=seed)
    if preset_name == "plushbound_guardian":
        request = apply_guardian_composition(request)
    request = apply_production_style(preset_name, request)
    request = apply_creature_world_policy(
        preset_name, request, creature_family=creature_family
    )

    if reference_id is not None:
        reference_id = str(reference_id).strip().lower()
        if not _REFERENCE_ID_RE.fullmatch(reference_id):
            raise ValueError("reference_id must be a lowercase SHA-256 hex digest")
        reference_scale = float(reference_scale)
        if not 0.0 <= reference_scale <= 1.0:
            raise ValueError("reference_scale must be between 0 and 1")
        request["reference_id"] = reference_id
        request["reference_scale"] = reference_scale
        request["reference_mode"] = "style"
        request["production_reference_validated_mode"] = "style"
    else:
        request["production_reference_validated_mode"] = None

    request["production_request_builder_version"] = PRODUCTION_REQUEST_BUILDER_VERSION
    return request
