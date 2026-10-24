"""Deterministic Atlas production planner.

Atlas owns deterministic production structure for Plushbound assets: required outputs,
job identity, ledger state, downstream packaging/manifest expectations, and QA
acceptance state. Atlas never directs, conditions, or collaborates in Vera's visual
creation process. Vera owns visual asset creation and art direction independently.
Atlas personality is presentation-only and cannot alter any production decision.
"""
from __future__ import annotations

import hashlib
import json

try:
    from .atlas_personality import ATLAS_PERSONALITY_VERSION, speak
    from .atlas_production_ledger import LEDGER_VERSION, new_record
    from .plushbound_brain import ASSISTANT_NAME, BRAIN_VERSION, WORLD_NAME, get_family_contract, missing_context
    from .production_request_builder import build_production_request
except ImportError:
    from atlas_personality import ATLAS_PERSONALITY_VERSION, speak
    from atlas_production_ledger import LEDGER_VERSION, new_record
    from plushbound_brain import ASSISTANT_NAME, BRAIN_VERSION, WORLD_NAME, get_family_contract, missing_context
    from production_request_builder import build_production_request

ATLAS_VERSION = "atlas-controller-v5-personality-isolated"
MAX_SEED = 2**63 - 1

RESPONSIBILITY_BOUNDARY = {
    "vera_owns_visual_creation": True,
    "vera_owns_art_direction": True,
    "atlas_owns_final_pixel_placement": True,
    "atlas_owns_slot_coordinates": True,
    "atlas_owns_canvas_geometry": True,
    "atlas_owns_manifest_mapping": True,
    "atlas_owns_version_validation": True,
    "atlas_owns_qa_acceptance_state": True,
    "atlas_may_direct_visual_generation": False,
    "atlas_may_condition_visual_generation": False,
    "atlas_may_override_vera_art_direction": False,
    "vera_may_override_atlas_geometry_or_manifest": False,
    "atlas_personality_is_presentation_only": True,
}


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _normalized_context(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("context must be an object")
    return {str(key): str(item).strip() for key, item in value.items() if str(item).strip()}


def _deterministic_seed(family: str, description: str, context: dict[str, str]) -> int:
    payload = _canonical({"family": family, "description": description, "context": context})
    value = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return value & MAX_SEED


def _build_prompt(description: str, family_rules: tuple[str, ...], context: dict[str, str]) -> str:
    parts = [description]
    if context:
        ordered = ", ".join(f"{key}: {context[key]}" for key in sorted(context))
        parts.append(f"Plushtopia production context: {ordered}")
    if family_rules:
        parts.append("Family contract: " + "; ".join(family_rules))
    return ". ".join(parts)


def _identity(family: str, description: str, context: dict[str, str], seed: int, request: dict | None) -> tuple[str, str]:
    material = {
        "atlas_version": ATLAS_VERSION,
        "brain_version": BRAIN_VERSION,
        "responsibility_boundary": RESPONSIBILITY_BOUNDARY,
        "family": family,
        "description": description,
        "context": context,
        "seed": seed,
        "generation_request": request,
    }
    plan_digest = hashlib.sha256(_canonical(material)).hexdigest()
    atlas_job_id = hashlib.sha256(f"{family}\0{plan_digest}".encode("utf-8")).hexdigest()[:24]
    return atlas_job_id, plan_digest


def plan_asset(intent: dict) -> dict:
    if not isinstance(intent, dict):
        raise ValueError("intent must be an object")
    family = str(intent.get("family", "")).strip()
    description = str(intent.get("description", "")).strip()
    if not family:
        raise ValueError("family is required")
    if not description:
        raise ValueError("description is required")

    contract = get_family_contract(family)
    context = _normalized_context(intent.get("context"))
    missing = missing_context(family, context)
    if missing:
        raise ValueError(f"missing required context for {family}: {', '.join(missing)}")

    supplied_seed = intent.get("seed")
    if supplied_seed is None:
        seed = _deterministic_seed(family, description, context)
        seed_source = "deterministic"
    else:
        seed = int(supplied_seed)
        if not 0 <= seed <= MAX_SEED:
            raise ValueError("seed must be between 0 and 2^63-1")
        seed_source = "provided"

    # This request describes the asset requirement only. Atlas does not choose Vera's
    # conditioning references, visual workflow, pose controls, or art-direction inputs.
    request = None
    if contract.production_preset is not None:
        prompt = _build_prompt(description, contract.rules, context)
        request = build_production_request(
            contract.production_preset,
            prompt,
            seed=seed,
            reference_id=intent.get("reference_id"),
            reference_scale=float(intent.get("reference_scale", 0.35)),
            creature_family=contract.creature_family,
        )

    atlas_job_id, plan_digest = _identity(family, description, context, seed, request)
    ledger_record = new_record(atlas_job_id, family, plan_digest).to_dict()
    atlas_voice = speak("plan_ready", subject=family.replace("_", " "))

    return {
        "assistant_name": ASSISTANT_NAME,
        "controller_version": ATLAS_VERSION,
        "personality_version": ATLAS_PERSONALITY_VERSION,
        "brain_version": BRAIN_VERSION,
        "ledger_version": LEDGER_VERSION,
        "world": WORLD_NAME,
        "atlas_job_id": atlas_job_id,
        "plan_digest": plan_digest,
        "family": family,
        "production_state": contract.production_state,
        "required_outputs": list(contract.required_outputs),
        "context": context,
        "seed": seed,
        "seed_source": seed_source,
        "generation_request": request,
        "generation_supported": request is not None,
        "responsibility_boundary": dict(RESPONSIBILITY_BOUNDARY),
        "visual_generation_owned_by": "Vera",
        "deterministic_compilation_owned_by": "Atlas",
        "atlas_visual_conditioning": None,
        "atlas_voice": atlas_voice,
        "ledger_record": ledger_record,
        "chat_model_attached": False,
        "automatic_full_production_authorized": False,
    }
