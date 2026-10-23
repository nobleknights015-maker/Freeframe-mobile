"""Single authority for building Plushbound production generation requests.

This composes the frozen asset preset, any asset-specific composition repair, and
only GPU-validated render-style policy. Batch launchers should use this builder so
rehearsal and future production runs cannot silently drift apart.
"""
from __future__ import annotations

from guardian_composition_policy import apply_guardian_composition
from production_presets import get_preset
from production_style_policy import apply_production_style

PRODUCTION_REQUEST_BUILDER_VERSION = "production-request-v1"


def build_production_request(preset_name: str, prompt: str, *, seed: int) -> dict:
    request = get_preset(preset_name).apply(prompt, seed=seed)
    if preset_name == "plushbound_guardian":
        request = apply_guardian_composition(request)
    request = apply_production_style(preset_name, request)
    request["production_request_builder_version"] = PRODUCTION_REQUEST_BUILDER_VERSION
    return request
