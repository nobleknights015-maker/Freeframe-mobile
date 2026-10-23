"""Production subject-extraction backend policy.

BiRefNet is the selected first backend for Plushbound. The policy is kept separate
from the provider implementation so model/runtime changes remain explicit and
auditable rather than leaking into the production factory.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionBackendPolicy:
    provider: str
    model: str
    inference_size: int
    preserve_source_canvas: bool
    output_mode: str
    license_family: str


PRODUCTION_EXTRACTION_BACKEND = ExtractionBackendPolicy(
    provider="birefnet",
    model="ZhengPeng7/BiRefNet",
    inference_size=1024,
    preserve_source_canvas=True,
    output_mode="rgba_cutout",
    license_family="MIT",
)

# RMBG-2.0 is intentionally not the default self-hosted production backend:
# its published weights are non-commercial unless separately licensed.
NON_DEFAULT_BACKENDS = {
    "briaai/RMBG-2.0": "commercial agreement required for commercial self-hosted use",
}


def production_extraction_backend() -> ExtractionBackendPolicy:
    return PRODUCTION_EXTRACTION_BACKEND
