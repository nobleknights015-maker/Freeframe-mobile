"""Deterministic RPG Maker MV sheet-layout helpers.

Generated art should arrive here as already-cleaned transparent cells. These
helpers calculate and validate exact grids; image-pixel compositing can use the
returned boxes without asking diffusion to understand engine sheet geometry.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GridSpec:
    columns: int
    rows: int
    cell_width: int
    cell_height: int

    @property
    def width(self) -> int:
        return self.columns * self.cell_width

    @property
    def height(self) -> int:
        return self.rows * self.cell_height

    def boxes(self) -> tuple[tuple[int, int, int, int], ...]:
        return tuple(
            (
                column * self.cell_width,
                row * self.cell_height,
                (column + 1) * self.cell_width,
                (row + 1) * self.cell_height,
            )
            for row in range(self.rows)
            for column in range(self.columns)
        )


MV_FACESET = GridSpec(columns=4, rows=2, cell_width=144, cell_height=144)


def regular_character_sheet(cell_width: int, cell_height: int) -> GridSpec:
    """Eight characters, each 3x4 frames, arranged in MV's 4x2 character grid."""
    _positive(cell_width, cell_height)
    return GridSpec(columns=12, rows=8, cell_width=cell_width, cell_height=cell_height)


def single_character_sheet(cell_width: int, cell_height: int) -> GridSpec:
    """One `$`-prefixed MV character sheet: 3 columns by 4 directions."""
    _positive(cell_width, cell_height)
    return GridSpec(columns=3, rows=4, cell_width=cell_width, cell_height=cell_height)


def validate_cells(spec: GridSpec, cells: int) -> None:
    expected = spec.columns * spec.rows
    if cells != expected:
        raise ValueError(f"expected {expected} cells, got {cells}")


def placement_manifest(spec: GridSpec, cell_names: list[str]) -> dict:
    """Return stable placement metadata for downstream Pillow/PNG compositing."""
    validate_cells(spec, len(cell_names))
    return {
        "width": spec.width,
        "height": spec.height,
        "columns": spec.columns,
        "rows": spec.rows,
        "placements": [
            {"name": name, "box": list(box)}
            for name, box in zip(cell_names, spec.boxes())
        ],
    }


def _positive(*values: int) -> None:
    if any(value <= 0 for value in values):
        raise ValueError("cell dimensions must be positive")
