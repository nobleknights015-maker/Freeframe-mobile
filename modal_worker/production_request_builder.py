"""Single authority for building Plushbound production generation requests."""
from __future__ import annotations
import re
try:
    from .creature_world_policy import apply_creature_world_policy, resolve_creature_family
    from .guardian_composition_policy import apply_guardian_composition
    from .production_presets import get_preset
    from .production_style_policy import apply_production_style
except ImportError:
    from creature_world_policy import apply_creature_world_policy, resolve_creature_family
    from guardian_composition_policy import apply_guardian_composition
    from production_presets import get_preset
    from production_style_policy import apply_production_style

PRODUCTION_REQUEST_BUILDER_VERSION = "production-request-v4-family-aware"
_REFERENCE_ID_RE = re.compile(r"^[0-9a-f]{64}$")

def build_production_request(preset_name: str,prompt: str,*,seed: int,reference_id: str|None=None,reference_scale: float=0.35,creature_family: str|None=None)->dict:
    resolved_family = resolve_creature_family(preset_name, creature_family)
    request = get_preset(preset_name).apply(prompt, seed=seed)
    if preset_name == "plushbound_guardian":
        request = apply_guardian_composition(request, creature_family=resolved_family or "guardian_friendly")
    request = apply_production_style(preset_name, request)
    request = apply_creature_world_policy(preset_name, request, creature_family=resolved_family)
    if reference_id is not None:
        reference_id=str(reference_id).strip().lower()
        if not _REFERENCE_ID_RE.fullmatch(reference_id): raise ValueError("reference_id must be a lowercase SHA-256 hex digest")
        reference_scale=float(reference_scale)
        if not 0.0 <= reference_scale <= 1.0: raise ValueError("reference_scale must be between 0 and 1")
        request["reference_id"]=reference_id; request["reference_scale"]=reference_scale; request["reference_mode"]="style"; request["production_reference_validated_mode"]="style"
    else: request["production_reference_validated_mode"]=None
    request["production_request_builder_version"]=PRODUCTION_REQUEST_BUILDER_VERSION
    return request
