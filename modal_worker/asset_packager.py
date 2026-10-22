"""Bridge cleaned PNG cells to deterministic RPG Maker MV packages."""
from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Iterable

from PIL import Image

from asset_profiles import validate_metadata
from mv_compositor import MV_FACESET, regular_character_sheet, single_character_sheet
from png_compositor import compose_rgba_sheet, inspect_composite


PACKAGE_VERSION = "plushbound-mv-packager-v1"


def package_single_character(cell_pngs: Iterable[bytes], *, cell_width: int, cell_height: int) -> dict:
    return _package(
        profile="mv_single_character",
        spec=single_character_sheet(cell_width, cell_height),
        cell_pngs=cell_pngs,
        filename_prefix="$",
    )


def package_regular_character(cell_pngs: Iterable[bytes], *, cell_width: int, cell_height: int) -> dict:
    return _package(
        profile="mv_character_sheet",
        spec=regular_character_sheet(cell_width, cell_height),
        cell_pngs=cell_pngs,
        filename_prefix="",
    )


def package_faceset(face_pngs: Iterable[bytes]) -> dict:
    return _package(profile="mv_faceset", spec=MV_FACESET, cell_pngs=face_pngs, filename_prefix="")


def _package(*, profile: str, spec, cell_pngs: Iterable[bytes], filename_prefix: str) -> dict:
    png = compose_rgba_sheet(spec, cell_pngs)
    composite = inspect_composite(png, spec)
    validation = validate_metadata(
        profile_name=profile,
        fmt=composite["format"],
        width=composite["width"],
        height=composite["height"],
        has_alpha=composite["has_alpha"],
    )
    if not validation["valid"]:
        raise ValueError("packaged asset failed engine validation: " + "; ".join(validation["errors"]))
    return {
        "png": png,
        "metadata": {
            "package_version": PACKAGE_VERSION,
            "profile": profile,
            "filename_prefix": filename_prefix,
            "width": composite["width"],
            "height": composite["height"],
            "has_alpha": composite["has_alpha"],
            "sha256": hashlib.sha256(png).hexdigest(),
            "bytes": len(png),
            "engine_validation": validation,
        },
    }


def inspect_png(png: bytes) -> dict:
    with Image.open(BytesIO(png)) as image:
        image.load()
        return {"format": image.format, "width": image.width, "height": image.height, "has_alpha": "A" in image.getbands()}
