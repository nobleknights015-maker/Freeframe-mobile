"""Fail-closed quality gate for promoting a model into Plushbound production."""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class PromotionPolicy:
    minimum_cases: int = 4
    minimum_integrity_rate: float = 1.0
    minimum_visual_score: float = 7.0
    maximum_failure_rate: float = 0.0
    maximum_projected_gpu_hours: float = 120.0


@dataclass(frozen=True)
class PromotionDecision:
    approved: bool
    reasons: tuple[str, ...]

    def metadata(self) -> dict:
        return asdict(self)


def evaluate(summary: dict, policy: PromotionPolicy = PromotionPolicy()) -> PromotionDecision:
    reasons: list[str] = []
    cases = int(summary.get("cases", 0))
    integrity_rate = float(summary.get("integrity_rate", 0.0))
    visual_score = float(summary.get("visual_score", 0.0))
    failure_rate = float(summary.get("failure_rate", 1.0))
    projected_hours = float(summary.get("projected_gpu_hours_22000", float("inf")))

    if cases < policy.minimum_cases:
        reasons.append(f"requires at least {policy.minimum_cases} representative cases")
    if integrity_rate < policy.minimum_integrity_rate:
        reasons.append("PNG/integrity checks are not perfect")
    if visual_score < policy.minimum_visual_score:
        reasons.append(f"visual score below {policy.minimum_visual_score:.1f}")
    if failure_rate > policy.maximum_failure_rate:
        reasons.append("benchmark contains generation failures")
    if projected_hours > policy.maximum_projected_gpu_hours:
        reasons.append("projected GPU time exceeds production ceiling")

    return PromotionDecision(approved=not reasons, reasons=tuple(reasons))
