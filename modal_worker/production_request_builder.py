"""Single authority for building Plushbound production generation requests.

This composes the frozen asset preset, any asset-specific composition repair,
GPU-validated render-style policy, and an optional approved visual-reference ID.
Batch launchers should use this builder so rehearsal and future production runs
cannot silently drift apart.
"""
from __future__ import annotations

import re

try:
    from .guardian_composition_policy import apply_guardian_composition
    from .production_presets import get_preset
    from .production_style_policy import apply_production_style
except ImportError:  # direct-module compatibility for local CI/tests
    from guardian_composition_policy import apply_guardian_composition
    from production_presets import get_preset
    from production_style_policy import apply_production_style

PRODUCTION_REQUEST_BUILDER_VERSION = "production-request-v2"
_REFERENCE_ID_RE = re.compile(r"^[0-9a-f]{64}$")


def build_production_request(
    preset_name: str,
    prompt: str,
    *,
    seed: int,
    reference_id: str | None = None,
    reference_scale: float = 0.35,
) -> dict:
    request = get_preset(preset_name).apply(prompt, seed=seed)
    if preset_name == "plushbound_guardian":
        request = apply_guardian_composition(request)
    request = apply_production_style(preset_name, request)

    if reference_id is not None:
        if not _REFERENCE_ID_RE.fullmatch(reference_id):
            raise ValueError("reference_id must be a lowercase SHA-256 hex digest")
        if not 0.0 <= float(reference_scale) <= 1.0:
            raise ValueError("reference_scale must be between 0.0 and 1.0")
        request["reference_id"] = reference_id
        request["reference_scale"] = float(reference_scale)
        # Production reference conditioning is deliberately style-only. Balanced
        # mode remains an experiment surface, not a mass-production default.
        request["reference_mode"] = "style"
        request["production_reference_validated_mode"] = "style"
    else:
        request["production_reference_validated_mode"] = None

    request["production_request_builder_version"] = PRODUCTION_REQUEST_BUILDER_VERSION
    return request
