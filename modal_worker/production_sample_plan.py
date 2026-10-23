"""Small real-GPU production sample plan before any large Plushbound batch.

This is intentionally tiny: enough to validate real generated masters against
the deterministic production machinery without opening the 22k-asset floodgate.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from production_presets import PLUSHBOUND_STYLE_VERSION


SAMPLE_PLAN_VERSION = "production-sample-v1"


@dataclass(frozen=True)
class ProductionSample:
    sample_id: str
    preset: str
    prompt: str
    seed: int
    purpose: str

    def metadata(self) -> dict:
        return {
            **asdict(self),
            "sample_plan_version": SAMPLE_PLAN_VERSION,
            "style_version": PLUSHBOUND_STYLE_VERSION,
        }


SAMPLES = (
    ProductionSample(
        "character_master",
        "plushbound_character",
        "adult Plushtopia field adventurer, practical layered travel clothes, leather satchel, calm neutral stance",
        8201,
        "Validate one-person anatomy, silhouette, cleanup readiness, and portrait/sprite source suitability.",
    ),
    ProductionSample(
        "guardian_master",
        "plushbound_guardian",
        "small foxlike living Guardian companion species with woven hide, subtle natural seam markings, expressive alert posture and gentle magical glow",
        8202,
        "Validate living companion-creature identity, anti-toy behavior, alpha-extraction readiness, and icon source suitability.",
    ),
    ProductionSample(
        "enemy_master",
        "plushbound_enemy",
        "mossback living-textile woodland prowler, low quadruped predator with woven hide, bark-like plates, thread-fiber mane and threatening hunting stance",
        8203,
        "Validate hostile living-textile identity, single-monster silhouette, artifact rejection, and battle-sprite source suitability.",
    ),
    ProductionSample(
        "elyndor_environment",
        "plushbound_environment",
        "sunny plains of Elyndor, broad flowered grasslands, winding road toward a distant hill settlement and landmark tower",
        8204,
        "Validate Plushtopia environment semantics and clean background packaging.",
    ),
)


def sample_manifest() -> dict:
    return {
        "sample_plan_version": SAMPLE_PLAN_VERSION,
        "style_version": PLUSHBOUND_STYLE_VERSION,
        "count": len(SAMPLES),
        "samples": [sample.metadata() for sample in SAMPLES],
    }
