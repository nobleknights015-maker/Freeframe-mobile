"""Explicit model candidates and model-aware inference defaults for FreeFrame.

A renderer can be eligible for bounded production without authorizing a catalog-wide
launch. Atlas and the worker still keep the 22k+ rollout behind separate QA/budget
and launch gates.
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


PRODUCTION_RENDERER_KEY = "flux2_klein_4b_candidate"


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
            "Legacy higher-quality candidate retained for comparison only. Never launch a large "
            "batch until benchmarked and explicitly promoted."
        ),
    ),
    "flux2_klein_4b_candidate": ModelCandidate(
        key="flux2_klein_4b_candidate",
        model_id="black-forest-labs/FLUX.2-klein-4B",
        dtype="bfloat16",
        default_steps=4,
        default_guidance=1.0,
        max_test_resolution=1024,
        production_eligible=True,
        notes=(
            "Promoted for bounded FreeFrame production jobs after L4 quality/cost validation. "
            "Apache-2.0 weights; roughly 13GB VRAM; four-step distilled inference; guidance 1.0. "
            "This promotion does not authorize the catalog-wide 22k+ launch."
        ),
    ),
    "flux2_klein_4b_fp8_candidate": ModelCandidate(
        key="flux2_klein_4b_fp8_candidate",
        model_id="black-forest-labs/FLUX.2-klein-4b-fp8",
        dtype="float8_e4m3fn",
        default_steps=4,
        default_guidance=1.0,
        max_test_resolution=1024,
        production_eligible=False,
        notes=(
            "Secondary low-memory benchmark candidate. Retained only as a fallback if the full BF16 "
            "renderer becomes unsuitable for the active GPU profile."
        ),
    ),
}


def get_candidate(key: str) -> ModelCandidate:
    try:
        return CANDIDATES[key]
    except KeyError as exc:
        raise ValueError(f"unknown model candidate: {key}") from exc


def get_production_renderer() -> ModelCandidate:
    candidate = get_candidate(PRODUCTION_RENDERER_KEY)
    if not candidate.production_eligible:
        raise RuntimeError("configured FreeFrame production renderer is not production eligible")
    return candidate


def apply_model_defaults(request: dict, candidate: ModelCandidate) -> dict:
    result = dict(request)
    result["steps"] = candidate.default_steps
    result["guidance_scale"] = candidate.default_guidance
    result["model_candidate"] = candidate.key
    result["model_id"] = candidate.model_id
    return result
