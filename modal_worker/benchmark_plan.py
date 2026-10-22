"""Small representative benchmark plan before any large Plushbound GPU batch."""
from __future__ import annotations

from dataclasses import dataclass, asdict

from production_presets import get_preset


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    preset: str
    prompt: str
    seed: int

    def request(self) -> dict:
        return get_preset(self.preset).apply(self.prompt, seed=self.seed)

    def metadata(self) -> dict:
        return asdict(self)


CASES = (
    BenchmarkCase(
        "guardian_meadow",
        "small foxlike stitched guardian with leaf-shaped ears and a warm amber charm, full body",
        "plushbound_guardian",
        1842,
    ),
    BenchmarkCase(
        "character_adventurer",
        "adult traveling adventurer, practical layered fantasy outfit, full body neutral pose",
        "plushbound_character",
        2718,
    ),
    BenchmarkCase(
        "enemy_forest",
        "mossy woodland prowler with wooden mask-like facial plating, full creature visible",
        "plushbound_enemy",
        3141,
    ),
    BenchmarkCase(
        "environment_elyndor",
        "sunny plains of Elyndor, rolling flower fields, distant village, ancient cloth banners and winding road",
        "plushbound_environment",
        5772,
    ),
)


def build_requests() -> list[dict]:
    return [case.request() for case in CASES]
