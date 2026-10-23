"""Budget guardrails for FreeFrame model-upgrade benchmarks.

This module deliberately separates benchmark economics from production approval.
Passing a budget check never authorizes a large production run.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


L4_GPU_USD_PER_SECOND = 0.000222
TARGET_MONTHLY_COMPUTE_USD = 30.0
HARD_MONTHLY_COMPUTE_CEILING_USD = 40.0
DEFAULT_PROJECTED_ASSETS = 22_000


@dataclass(frozen=True)
class BudgetProjection:
    average_seconds_per_image: float
    projected_assets: int
    gpu_rate_usd_per_second: float
    projected_raw_gpu_usd: float
    target_monthly_compute_usd: float
    hard_monthly_compute_ceiling_usd: float
    within_target: bool
    within_hard_ceiling: bool

    def metadata(self) -> dict:
        return asdict(self)


def project_budget(
    average_seconds_per_image: float,
    *,
    projected_assets: int = DEFAULT_PROJECTED_ASSETS,
    gpu_rate_usd_per_second: float = L4_GPU_USD_PER_SECOND,
    target_monthly_compute_usd: float = TARGET_MONTHLY_COMPUTE_USD,
    hard_monthly_compute_ceiling_usd: float = HARD_MONTHLY_COMPUTE_CEILING_USD,
) -> BudgetProjection:
    if average_seconds_per_image < 0:
        raise ValueError("average_seconds_per_image must not be negative")
    if projected_assets <= 0:
        raise ValueError("projected_assets must be positive")
    if gpu_rate_usd_per_second <= 0:
        raise ValueError("gpu_rate_usd_per_second must be positive")
    if target_monthly_compute_usd <= 0:
        raise ValueError("target_monthly_compute_usd must be positive")
    if hard_monthly_compute_ceiling_usd < target_monthly_compute_usd:
        raise ValueError("hard ceiling must be greater than or equal to target")

    projected = average_seconds_per_image * projected_assets * gpu_rate_usd_per_second
    return BudgetProjection(
        average_seconds_per_image=round(average_seconds_per_image, 3),
        projected_assets=projected_assets,
        gpu_rate_usd_per_second=gpu_rate_usd_per_second,
        projected_raw_gpu_usd=round(projected, 2),
        target_monthly_compute_usd=target_monthly_compute_usd,
        hard_monthly_compute_ceiling_usd=hard_monthly_compute_ceiling_usd,
        within_target=projected <= target_monthly_compute_usd,
        within_hard_ceiling=projected <= hard_monthly_compute_ceiling_usd,
    )


def benchmark_decision(average_seconds_per_image: float) -> dict:
    """Return a fail-closed economics decision for a measured benchmark.

    This is raw GPU generation cost only. CPU, memory, extraction, retries, and
    other overhead remain outside this estimate, so production still requires a
    separate explicit approval gate.
    """
    projection = project_budget(average_seconds_per_image)
    if projection.within_target:
        status = "target"
    elif projection.within_hard_ceiling:
        status = "caution"
    else:
        status = "reject"
    return {
        **projection.metadata(),
        "status": status,
        "production_authorized": False,
    }
