"""Explicit model candidates and model-aware inference defaults for FreeFrame.

A candidate must be deliberately promoted before it is used for large production
runs. This keeps experimental quality tests from silently changing the 22k-asset
pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class ModelCandidate:
    key: str
    model_id: str
    dtype: str
    default_steps: int
    default_guidance: float
    max_test_resolution: int
    production_eligible: bool
    notes: str

    def metadata(self) -> dict:
        return asdict(self)


CANDIDATES = {
    "sd_turbo_smoke": ModelCandidate(
        key="sd_turbo_smoke",
        model_id="stabilityai/sd-turbo",
        dtype="float16",
        default_steps=4,
        default_guidance=0.0,
        max_test_resolution=512,
        production_eligible=False,
        notes="Known-working smoke-test model; retained only as infrastructure baseline.",
    ),
    "flux_schnell_candidate": ModelCandidate(
        key="flux_schnell_candidate",
        model_id="black-forest-labs/FLUX.1-schnell",
        dtype="bfloat16",
        default_steps=4,
        default_guidance=0.0,
        max_test_resolution=1024,
        production_eligible=False,
        notes=(
            "Higher-quality candidate for controlled evaluation. Model access may require "
            "Hugging Face acceptance/authentication. Never launch a large batch until benchmarked."
        ),
    ),
}


def get_candidate(key: str) -> ModelCandidate:
    try:
        return CANDIDATES[key]
    except KeyError as exc:
        raise ValueError(f"unknown model candidate: {key}") from exc


def apply_model_defaults(request: dict, candidate: ModelCandidate) -> dict:
    result = dict(request)
    result["steps"] = candidate.default_steps
    result["guidance_scale"] = candidate.default_guidance
    result["model_candidate"] = candidate.key
    result["model_id"] = candidate.model_id
    return result
