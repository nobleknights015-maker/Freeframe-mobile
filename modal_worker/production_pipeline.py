"""Deterministic post-generation checks for Plushbound production assets.

This layer sits between diffusion output and engine packaging. It does not ask
the model to produce exact RPG Maker sheets; it classifies generated masters,
normalizes them, and rejects obvious composition artifacts before deterministic
sheet/tile compositing.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

from extraction_routing import requires_subject_extraction


AssetClass = Literal[
    "character_master",
    "guardian_master",
    "enemy_master",
    "environment_master",
    "portrait_master",
    "sprite_master",
    "tileset_master",
    "icon_master",
]


@dataclass(frozen=True)
class ProductionPolicy:
    asset_class: AssetClass
    require_png: bool = True
    require_alpha: bool = False
    allow_border: bool = False
    allow_text: bool = False
    single_subject: bool = False
    outdoor_only: bool = False
    target_aspect: str = "free"


POLICIES: dict[str, ProductionPolicy] = {
    "character_master": ProductionPolicy("character_master", single_subject=True, target_aspect="3:4"),
    "guardian_master": ProductionPolicy("guardian_master", single_subject=True, target_aspect="1:1"),
    "enemy_master": ProductionPolicy("enemy_master", single_subject=True, target_aspect="1:1"),
    "environment_master": ProductionPolicy("environment_master", outdoor_only=True, target_aspect="4:3"),
    "portrait_master": ProductionPolicy("portrait_master", single_subject=True, target_aspect="1:1"),
    "sprite_master": ProductionPolicy("sprite_master", require_alpha=True, single_subject=True),
    "tileset_master": ProductionPolicy("tileset_master", require_alpha=True),
    "icon_master": ProductionPolicy("icon_master", single_subject=True, target_aspect="1:1"),
}


@dataclass(frozen=True)
class InspectionResult:
    accepted: bool
    asset_class: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    needs_background_removal: bool
    needs_border_cleanup: bool
    needs_text_cleanup: bool

    def to_dict(self) -> dict:
        return asdict(self)


def inspect_master(
    *,
    asset_class: str,
    fmt: str,
    width: int,
    height: int,
    has_alpha: bool,
    border_detected: bool = False,
    text_artifact_detected: bool = False,
    subject_count: int | None = None,
    indoor_detected: bool = False,
) -> InspectionResult:
    """Apply deterministic/externally measured facts to a production policy.

    Visual detectors are intentionally inputs: this keeps policy decisions cheap,
    testable and independent from whichever detector we later choose.
    """
    policy = POLICIES.get(asset_class)
    if policy is None:
        return InspectionResult(False, asset_class, (f"unknown asset class: {asset_class}",), (), False, False, False)

    errors: list[str] = []
    warnings: list[str] = []
    if policy.require_png and fmt.upper() != "PNG":
        errors.append("master must be PNG")
    if width <= 0 or height <= 0:
        errors.append("master dimensions must be positive")
    if policy.single_subject and subject_count is not None and subject_count != 1:
        errors.append(f"expected one subject, detected {subject_count}")
    if policy.outdoor_only and indoor_detected:
        errors.append("environment master appears to be indoors")
    if border_detected and not policy.allow_border:
        warnings.append("decorative border requires cleanup")
    if text_artifact_detected and not policy.allow_text:
        warnings.append("text-like artifact requires cleanup")

    # Raw subject masters deliberately route through semantic extraction even when
    # their PNG container happens to carry an opaque alpha channel. Scene masters
    # and downstream composites do not. This is the single routing authority.
    needs_background_removal = requires_subject_extraction(asset_class)
    if needs_background_removal:
        warnings.append("subject master requires semantic background removal")
    elif policy.require_alpha and not has_alpha:
        warnings.append("downstream engine asset requires alpha before packaging")

    return InspectionResult(
        accepted=not errors,
        asset_class=asset_class,
        errors=tuple(errors),
        warnings=tuple(warnings),
        needs_background_removal=needs_background_removal,
        needs_border_cleanup=border_detected and not policy.allow_border,
        needs_text_cleanup=text_artifact_detected and not policy.allow_text,
    )


def production_stage(asset_class: str) -> str:
    """Describe the next deterministic stage after a clean generated master."""
    if asset_class in {"sprite_master", "tileset_master"}:
        return "composite_and_validate_engine_sheet"
    if requires_subject_extraction(asset_class):
        return "cleanup_extract_and_package"
    if asset_class == "environment_master":
        return "cleanup_resize_and_package"
    raise ValueError(f"unknown asset class: {asset_class}")
