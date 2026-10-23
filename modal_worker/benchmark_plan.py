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
            "Penney Nguyen, clearly adult woman age 25, petite 4 foot 11 inch height and naturally plump proportional build, "
            "original Plushbound Legends field-adventurer design, short black bob haircut, expressive dark eyes, "
            "violet fitted travel tunic with asymmetric wrapped front, cropped charcoal bolero jacket with subtle stitched trim, "
            "layered utility belt and small leather pouches, fitted black travel shorts over opaque dark thigh wraps, "
            "knee-high brown lace-up field boots, restrained brass hardware, tiny spool-and-thread motif worked into one belt charm, "
            "handcrafted fantasy tailoring that feels practical rather than cosplay, confident relaxed stance, full body visible, "
            "both hands fully visible with natural fingers, normal anatomy, one original character only, no logo and no text"
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
