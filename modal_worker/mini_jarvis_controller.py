"""Deterministic Mini-Jarvis production planner.

This is stage one of the in-app assistant: it plans against plushbound_brain and the
same production_request_builder used by batch generation. A future compact language
model can translate chat into the structured intent accepted here; it does not own
or override production rules.
"""
from __future__ import annotations

import hashlib
import json

try:
    from .plushbound_brain import BRAIN_VERSION, WORLD_NAME, get_family_contract, missing_context
    from .production_request_builder import build_production_request
except ImportError:
    from plushbound_brain import BRAIN_VERSION, WORLD_NAME, get_family_contract, missing_context
    from production_request_builder import build_production_request

MINI_JARVIS_VERSION = "mini-jarvis-controller-v1"
MAX_SEED = 2**63 - 1


def _normalized_context(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("context must be an object")
    return {str(key): str(item).strip() for key, item in value.items() if str(item).strip()}


def _deterministic_seed(family: str, description: str, context: dict[str, str]) -> int:
    payload = json.dumps({"family": family, "description": description, "context": context}, sort_keys=True, separators=(",", ":")).encode("utf-8")
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

    return {
        "controller_version": MINI_JARVIS_VERSION,
        "brain_version": BRAIN_VERSION,
        "world": WORLD_NAME,
        "family": family,
        "production_state": contract.production_state,
        "required_outputs": list(contract.required_outputs),
        "context": context,
        "seed": seed,
        "seed_source": seed_source,
        "generation_request": request,
        "generation_supported": request is not None,
        "chat_model_attached": False,
        "automatic_full_production_authorized": False,
    }
