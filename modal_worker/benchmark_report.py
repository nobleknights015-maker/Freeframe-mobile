"""Deterministic benchmark accounting for FreeFrame model evaluations."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import mean


@dataclass(frozen=True)
class BenchmarkResult:
    case_id: str
    elapsed_seconds: float
    valid_png: bool
    width: int
    height: int
    bytes: int
    sha256: str
    model: str
    seed: int
    visual_score: float | None = None

    def metadata(self) -> dict:
        return asdict(self)


def summarize(results: list[BenchmarkResult], *, projected_assets: int = 22_000) -> dict:
    if not results:
        raise ValueError("benchmark requires at least one result")
    if projected_assets <= 0:
        raise ValueError("projected_assets must be positive")
    invalid = [r.case_id for r in results if not r.valid_png]
    times = [r.elapsed_seconds for r in results]
    if any(t < 0 for t in times):
        raise ValueError("elapsed_seconds must not be negative")
    avg = mean(times)
    visual = [r.visual_score for r in results if r.visual_score is not None]
    return {
        "cases": len(results),
        "invalid_cases": invalid,
        "average_inference_seconds": round(avg, 3),
        "slowest_inference_seconds": round(max(times), 3),
        "projected_assets": projected_assets,
        "projected_raw_gpu_hours": round(avg * projected_assets / 3600, 2),
        "average_visual_score": round(mean(visual), 2) if visual else None,
        "models": sorted({r.model for r in results}),
    }
