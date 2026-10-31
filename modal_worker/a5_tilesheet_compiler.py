"""Deterministic Plushbound WORLD_TILE_ASSET_V1 compiler.

This module owns runtime geometry only. It never resizes, crops, extracts,
infers, generates, or visually repairs artwork. Vera-approved PNG pixels enter
as immutable 48x48 or 96x96 sources and are placed only at manifest-declared,
deterministically validated coordinates.
"""
from __future__ import annotations

import hashlib
import io
import json
from typing import Mapping

from PIL import Image

TILE_SIZE = 48
COLUMNS = 8
ROWS = 16
SLOT_COUNT = COLUMNS * ROWS
CANVAS_WIDTH = COLUMNS * TILE_SIZE
CANVAS_HEIGHT = ROWS * TILE_SIZE
SCHEMA = "plushbound.world_tile_sheet.v1"
TEMPLATE_VERSION = "WORLD_TILE_ASSET_V1"
PROVENANCE = "vera-chatgpt-approved"
APPROVAL_DESIGNATION = "VERA_APPROVED_SOURCE_V1"
COMPILER_VERSION = "plushbound-world-tile-deterministic-v2"

ROLE_BANDS = (
    (0, 31, "a1_floor"),
    (32, 55, "a2_wall"),
    (56, 79, "a3_edge_corner"),
    (80, 103, "a4_prop"),
    (104, 127, "a5_variation"),
)
ALLOWED_FOOTPRINTS = {(1, 1), (2, 2)}


def _role_for_slot(slot_index: int) -> str:
    for start, end, role in ROLE_BANDS:
        if start <= slot_index <= end:
            return role
    raise ValueError(f"slot_index out of range: {slot_index}")


def _require_nonempty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _load_exact_source(raw: bytes, *, asset_id: str, footprint: tuple[int, int]) -> Image.Image:
    expected = (TILE_SIZE * footprint[0], TILE_SIZE * footprint[1])
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.format != "PNG":
                raise ValueError(f"{asset_id}: source must be PNG")
            if image.mode not in {"RGB", "RGBA"}:
                raise ValueError(f"{asset_id}: source mode must be RGB or RGBA; got {image.mode}")
            if image.size != expected:
                raise ValueError(
                    f"{asset_id}: footprint {list(footprint)} requires exact source size "
                    f"{expected[0]}x{expected[1]}; got {image.width}x{image.height}"
                )
            return image.convert("RGBA")
    except OSError as exc:
        raise ValueError(f"{asset_id}: invalid PNG payload") from exc


def validate_world_tile_manifest(manifest: Mapping[str, object]) -> None:
    """Validate the complete locked manifest, including 2x2 occupancy semantics."""
    exact_top_level = {
        "schema": SCHEMA,
        "template_version": TEMPLATE_VERSION,
        "canvas_width": CANVAS_WIDTH,
        "canvas_height": CANVAS_HEIGHT,
        "tile_size": TILE_SIZE,
        "columns": COLUMNS,
        "rows": ROWS,
        "provenance": PROVENANCE,
        "generator_calls_allowed": False,
        "gpu_allowed": False,
    }
    for field, expected in exact_top_level.items():
        if manifest.get(field) != expected:
            raise ValueError(f"{field} must be exactly {expected!r}")

    _require_nonempty_string(manifest.get("sheet_id"), "sheet_id")
    _require_nonempty_string(manifest.get("material_id"), "material_id")

    slots = manifest.get("slots")
    if not isinstance(slots, list) or len(slots) != SLOT_COUNT:
        count = len(slots) if isinstance(slots, list) else "non-list"
        raise ValueError(f"slots must contain exactly {SLOT_COUNT} entries; got {count}")

    asset_ids: set[str] = set()
    anchor_coverage: dict[int, str] = {}

    # First pass validates fixed geometry and anchor declarations.
    for expected_index, row in enumerate(slots):
        if not isinstance(row, dict):
            raise ValueError(f"slot {expected_index}: entry must be an object")

        expected_row = expected_index // COLUMNS
        expected_column = expected_index % COLUMNS
        expected_x = expected_column * TILE_SIZE
        expected_y = expected_row * TILE_SIZE
        expected_geometry = {
            "slot_index": expected_index,
            "row": expected_row,
            "column": expected_column,
            "x": expected_x,
            "y": expected_y,
        }
        for field, expected in expected_geometry.items():
            if row.get(field) != expected:
                raise ValueError(f"slot {expected_index}: {field} must be exactly {expected}")

        role = row.get("role")
        asset_id = row.get("asset_id")
        source_path = row.get("source_path")
        covered_by = row.get("covered_by")

        if role == "empty":
            if asset_id is not None or source_path is not None or covered_by is not None:
                raise ValueError(f"slot {expected_index}: empty slot must not carry asset/source/coverage")
            if row.get("footprint_tiles") not in (None, [1, 1]):
                raise ValueError(f"slot {expected_index}: empty slot cannot declare a multi-tile footprint")
            continue

        band_role = _role_for_slot(expected_index)
        if role != band_role:
            raise ValueError(f"slot {expected_index}: role must be {band_role!r} or 'empty'")

        # Covered cells carry only their anchor reference. The second pass proves it.
        if covered_by is not None:
            _require_nonempty_string(covered_by, f"slot {expected_index}.covered_by")
            if asset_id is not None or source_path is not None:
                raise ValueError(f"slot {expected_index}: covered slot must not duplicate asset_id/source_path")
            if row.get("footprint_tiles") is not None:
                raise ValueError(f"slot {expected_index}: covered slot must not declare footprint_tiles")
            continue

        asset_id = _require_nonempty_string(asset_id, f"slot {expected_index}.asset_id")
        _require_nonempty_string(source_path, f"slot {expected_index}.source_path")
        if asset_id in asset_ids:
            raise ValueError(f"duplicate non-empty asset_id: {asset_id}")
        asset_ids.add(asset_id)

        if row.get("approval_status") != "approved":
            raise ValueError(f"{asset_id}: approval_status must be 'approved'")
        if row.get("approval_designation") != APPROVAL_DESIGNATION:
            raise ValueError(f"{asset_id}: approval_designation must be {APPROVAL_DESIGNATION}")
        if row.get("production_authorized") is not True:
            raise ValueError(f"{asset_id}: production_authorized must be true")
        if row.get("provenance", PROVENANCE) != PROVENANCE:
            raise ValueError(f"{asset_id}: invalid provenance")
        if "target_size" in row:
            raise ValueError(f"{asset_id}: target_size is forbidden; compiler never resizes")

        footprint_value = row.get("footprint_tiles", [1, 1])
        if not (
            isinstance(footprint_value, list)
            and len(footprint_value) == 2
            and all(isinstance(v, int) for v in footprint_value)
        ):
            raise ValueError(f"{asset_id}: footprint_tiles must be [1, 1] or [2, 2]")
        footprint = tuple(footprint_value)
        if footprint not in ALLOWED_FOOTPRINTS:
            raise ValueError(f"{asset_id}: footprint_tiles must be [1, 1] or [2, 2]")

        width_tiles, height_tiles = footprint
        if expected_column + width_tiles > COLUMNS or expected_row + height_tiles > ROWS:
            raise ValueError(f"{asset_id}: footprint would leave the locked 8x16 grid")

        covered_indices: list[int] = []
        for dy in range(height_tiles):
            for dx in range(width_tiles):
                index = (expected_row + dy) * COLUMNS + (expected_column + dx)
                if _role_for_slot(index) != band_role:
                    raise ValueError(f"{asset_id}: footprint may not cross a locked role-band boundary")
                if index != expected_index:
                    if index in anchor_coverage:
                        raise ValueError(
                            f"{asset_id}: footprint overlaps coverage owned by {anchor_coverage[index]} at slot {index}"
                        )
                    anchor_coverage[index] = asset_id
                    covered_indices.append(index)

    # Second pass requires every footprint-covered cell to explicitly name its anchor,
    # and rejects orphan covered_by declarations.
    for index, row in enumerate(slots):
        if not isinstance(row, dict):
            raise AssertionError("validated above")
        expected_owner = anchor_coverage.get(index)
        declared_owner = row.get("covered_by")
        if expected_owner is not None:
            if declared_owner != expected_owner:
                raise ValueError(
                    f"slot {index}: must declare covered_by={expected_owner!r} for multi-tile footprint"
                )
        elif declared_owner is not None:
            raise ValueError(f"slot {index}: orphan covered_by declaration {declared_owner!r}")


def compile_world_tile_sheet(
    manifest: Mapping[str, object], tile_pngs: Mapping[str, bytes]
) -> dict[str, object]:
    """Compile an immutable 384x768 runtime sheet from a validated manifest."""
    validate_world_tile_manifest(manifest)
    slots = manifest["slots"]
    assert isinstance(slots, list)

    declared_ids = {
        row["asset_id"]
        for row in slots
        if isinstance(row, dict) and isinstance(row.get("asset_id"), str)
    }
    unexpected = set(tile_pngs) - declared_ids
    if unexpected:
        raise ValueError(f"undeclared source assets supplied: {sorted(unexpected)}")

    canvas = Image.new("RGBA", (CANVAS_WIDTH, CANVAS_HEIGHT), (0, 0, 0, 0))
    source_hashes: dict[str, str] = {}

    for row in slots:
        assert isinstance(row, dict)
        asset_id = row.get("asset_id")
        if not isinstance(asset_id, str):
            continue
        if asset_id not in tile_pngs:
            raise ValueError(f"missing approved source PNG for {asset_id}")

        footprint_value = row.get("footprint_tiles", [1, 1])
        assert isinstance(footprint_value, list)
        footprint = (int(footprint_value[0]), int(footprint_value[1]))
        source_raw = tile_pngs[asset_id]
        source = _load_exact_source(source_raw, asset_id=asset_id, footprint=footprint)
        canvas.paste(source, (int(row["x"]), int(row["y"])), source if source.mode == "RGBA" else None)
        source_hashes[asset_id] = hashlib.sha256(source_raw).hexdigest()

    output = io.BytesIO()
    canvas.save(output, format="PNG", optimize=False)
    raw = output.getvalue()

    with Image.open(io.BytesIO(raw)) as check:
        check.load()
        if check.format != "PNG" or check.size != (CANVAS_WIDTH, CANVAS_HEIGHT):
            raise RuntimeError("compiled output violated locked PNG geometry")
        if check.mode not in {"RGB", "RGBA"}:
            raise RuntimeError("compiled output violated locked color mode")

    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "png": raw,
        "manifest": manifest,
        "metadata": {
            "schema": SCHEMA,
            "template_version": TEMPLATE_VERSION,
            "compiler_version": COMPILER_VERSION,
            "format": "PNG",
            "width": CANVAS_WIDTH,
            "height": CANVAS_HEIGHT,
            "tile_width": TILE_SIZE,
            "tile_height": TILE_SIZE,
            "columns": COLUMNS,
            "rows": ROWS,
            "slot_count": SLOT_COUNT,
            "grid_origin": [0, 0],
            "margins": 0,
            "padding": 0,
            "resized_after_generation": False,
            "layout_inferred_visually": False,
            "reference_sheet_pixels_used_as_runtime_art": False,
            "png_sha256": hashlib.sha256(raw).hexdigest(),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "source_png_sha256": source_hashes,
        },
    }


def compile_a5_from_manifest(
    manifest: Mapping[str, object], tile_pngs: Mapping[str, bytes]
) -> dict[str, object]:
    """Compatibility name for callers; now enforces WORLD_TILE_ASSET_V1 fully."""
    return compile_world_tile_sheet(manifest, tile_pngs)
