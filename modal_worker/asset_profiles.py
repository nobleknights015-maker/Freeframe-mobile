"""Cheap deterministic validation for FreeFrame game assets."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AssetProfile:
    name: str
    require_png: bool = True
    require_alpha: bool = True
    exact_width: Optional[int] = None
    exact_height: Optional[int] = None
    width_multiple: Optional[int] = None
    height_multiple: Optional[int] = None


PROFILES = {
    # RPG Maker MV face sheets are conventionally 4x2 cells of 144x144.
    "mv_faceset": AssetProfile("mv_faceset", exact_width=576, exact_height=288),
    # Standard A-series tilesets have fixed MV dimensions.
    "mv_tileset_a1_a2": AssetProfile("mv_tileset_a1_a2", exact_width=768, exact_height=576),
    "mv_tileset_a3": AssetProfile("mv_tileset_a3", exact_width=768, exact_height=384),
    "mv_tileset_a4": AssetProfile("mv_tileset_a4", exact_width=768, exact_height=720),
    "mv_tileset_a5": AssetProfile("mv_tileset_a5", exact_width=384, exact_height=768),
    "mv_tileset_b_e": AssetProfile("mv_tileset_b_e", exact_width=768, exact_height=768),
    # Plushbound editor contract: regular sheets use eight 3x4 actors at 48x48 per frame.
    "mv_character_sheet": AssetProfile("mv_character_sheet", exact_width=576, exact_height=384),
    # Plushbound editor contract: one $-prefixed actor, 3x4 frames at exactly 48x48.
    "mv_single_character": AssetProfile("mv_single_character", exact_width=144, exact_height=192),
    "generic_rgba_png": AssetProfile("generic_rgba_png"),
}


def validate_metadata(*, profile_name: str, fmt: str, width: int, height: int, has_alpha: bool) -> dict:
    profile = PROFILES.get(profile_name)
    if profile is None:
        return {"valid": False, "errors": [f"unknown asset profile: {profile_name}"]}

    errors: list[str] = []
    if profile.require_png and fmt.upper() != "PNG":
        errors.append("asset must be PNG")
    if profile.require_alpha and not has_alpha:
        errors.append("asset must contain an alpha channel")
    if profile.exact_width is not None and width != profile.exact_width:
        errors.append(f"width must be {profile.exact_width}")
    if profile.exact_height is not None and height != profile.exact_height:
        errors.append(f"height must be {profile.exact_height}")
    if profile.width_multiple and width % profile.width_multiple:
        errors.append(f"width must be divisible by {profile.width_multiple}")
    if profile.height_multiple and height % profile.height_multiple:
        errors.append(f"height must be divisible by {profile.height_multiple}")
    return {"valid": not errors, "profile": profile_name, "errors": errors}
