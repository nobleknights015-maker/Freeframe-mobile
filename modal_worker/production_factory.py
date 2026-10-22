"""Deterministic production factory connecting cleanup-ready cells to MV packages.

Generation/background removal remain separate concerns. This layer accepts PNG
cells that have already passed semantic inspection and, when required, alpha
extraction. It normalizes every cell, packages the sheet, and records all
transforms for reproducibility.
"""
from __future__ import annotations

from typing import Iterable

from asset_packager import package_faceset, package_regular_character, package_single_character
from image_normalizer import normalize_rgba_cell


FACTORY_VERSION = "plushbound-production-factory-v1"


def build_single_character(
    cell_pngs: Iterable[bytes], *, cell_width: int = 48, cell_height: int = 48, padding: int = 1
) -> dict:
    normalized, transforms = _normalize_cells(cell_pngs, 12, cell_width, cell_height, padding)
    package = package_single_character(normalized, cell_width=cell_width, cell_height=cell_height)
    return _finish(package, transforms)


def build_regular_character(
    cell_pngs: Iterable[bytes], *, cell_width: int = 48, cell_height: int = 48, padding: int = 1
) -> dict:
    normalized, transforms = _normalize_cells(cell_pngs, 96, cell_width, cell_height, padding)
    package = package_regular_character(normalized, cell_width=cell_width, cell_height=cell_height)
    return _finish(package, transforms)


def build_faceset(face_pngs: Iterable[bytes], *, padding: int = 0) -> dict:
    normalized, transforms = _normalize_cells(face_pngs, 8, 144, 144, padding)
    package = package_faceset(normalized)
    return _finish(package, transforms)


def _normalize_cells(cell_pngs, expected_count, width, height, padding):
    payloads = list(cell_pngs)
    if len(payloads) != expected_count:
        raise ValueError(f"expected {expected_count} source cells, got {len(payloads)}")
    normalized = []
    transforms = []
    for index, payload in enumerate(payloads):
        png, transform = normalize_rgba_cell(
            payload,
            target_width=width,
            target_height=height,
            crop_transparent=True,
            padding=padding,
        )
        normalized.append(png)
        transforms.append({"cell_index": index, **transform})
    return normalized, transforms


def _finish(package: dict, transforms: list[dict]) -> dict:
    metadata = {
        **package["metadata"],
        "factory_version": FACTORY_VERSION,
        "cell_transforms": transforms,
        "cell_count": len(transforms),
    }
    return {"png": package["png"], "metadata": metadata}
