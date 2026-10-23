"""Small representative benchmark plan before any large Plushbound GPU batch."""
from __future__ import annotations

from dataclasses import dataclass, asdict

from modal_worker.production_presets import get_preset


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
        case_id="guardian_meadow",
        preset="plushbound_guardian",
        prompt="small foxlike stitched guardian with leaf-shaped ears and a warm amber charm, full body",
        seed=1842,
    ),
    BenchmarkCase(
        case_id="character_adventurer",
        preset="plushbound_character",
        prompt="adult traveling adventurer, practical layered fantasy outfit, full body neutral pose",
        seed=2718,
    ),
    BenchmarkCase(
        case_id="penney_modeling_stress",
        preset="plushbound_character",
        prompt=(
            "Penney Nguyen, clearly adult woman age 25, accurate 4 foot 11 inch petite height, "
            "naturally plump proportional build, fitted black spandex shorts and a fitted violet "
            "sleeveless athletic crop top, tasteful confident fashion-model pose, full body from "
            "head through feet, both hands fully visible, natural fingers and limbs, anatomically "
            "normal body, clean single-person composition, mature non-explicit modeling presentation"
        ),
        seed=6116,
    ),
    BenchmarkCase(
        case_id="enemy_forest",
        preset="plushbound_enemy",
        prompt="mossy woodland prowler with wooden mask-like facial plating, full creature visible",
        seed=3141,
    ),
    BenchmarkCase(
        case_id="environment_elyndor",
        preset="plushbound_environment",
        prompt="sunny plains of Elyndor, rolling flower fields, distant village, ancient cloth banners and winding road",
        seed=5772,
    ),
)


def build_requests() -> list[dict]:
    return [case.request() for case in CASES]
