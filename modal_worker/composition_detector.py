"""Cheap deterministic detector for obvious multi-panel/model-sheet compositions.

This is intentionally conservative. It does not try to understand semantics; it
looks for abnormally strong, image-spanning horizontal/vertical separators that
are characteristic of generated contact sheets and multi-view grids.
"""
from __future__ import annotations

from io import BytesIO
from statistics import median

from PIL import Image

PANEL_DETECTOR_VERSION = "panel-grid-v1"
RESIZE = 256
MIN_SEPARATOR_DELTA = 24.0
MIN_SEPARATOR_RATIO = 8.0


def _axis_edge_scores(gray: Image.Image) -> tuple[list[float], list[float]]:
    image = gray.resize((RESIZE, RESIZE), Image.Resampling.BILINEAR)
    pixels = list(image.getdata())
    width, height = image.size

    rows: list[float] = []
    for y in range(height - 1):
        here = y * width
        below = (y + 1) * width
        rows.append(sum(abs(pixels[here + x] - pixels[below + x]) for x in range(width)) / width)

    cols: list[float] = []
    for x in range(width - 1):
        cols.append(
            sum(abs(pixels[y * width + x] - pixels[y * width + x + 1]) for y in range(height)) / height
        )
    return rows, cols


def _axis_summary(values: list[float]) -> dict[str, float]:
    margin = max(1, int(len(values) * 0.08))
    interior = values[margin:-margin] or values
    baseline = float(median(interior))
    peak = float(max(interior))
    ratio = peak / max(baseline, 1e-6)
    return {"peak": peak, "median": baseline, "ratio": ratio}


def inspect_panel_grid(png: bytes) -> dict:
    with Image.open(BytesIO(png)) as image:
        image.load()
        if (image.format or "").upper() != "PNG":
            raise ValueError("panel detector requires PNG input")
        rows, cols = _axis_edge_scores(image.convert("L"))

    row = _axis_summary(rows)
    col = _axis_summary(cols)
    row_hit = row["peak"] >= MIN_SEPARATOR_DELTA and row["ratio"] >= MIN_SEPARATOR_RATIO
    col_hit = col["peak"] >= MIN_SEPARATOR_DELTA and col["ratio"] >= MIN_SEPARATOR_RATIO
    return {
        "detector_version": PANEL_DETECTOR_VERSION,
        "panel_grid_detected": bool(row_hit or col_hit),
        "row": row,
        "column": col,
        "thresholds": {
            "minimum_separator_delta": MIN_SEPARATOR_DELTA,
            "minimum_separator_ratio": MIN_SEPARATOR_RATIO,
        },
    }
