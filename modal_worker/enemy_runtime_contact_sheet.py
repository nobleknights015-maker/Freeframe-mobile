"""Build deterministic visual-QA contact sheets for one enemy runtime region."""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CELL = 288
TILE = 24
COLUMNS = 4
ROWS = 4
LABEL_HEIGHT = 20
CELL_PAD = 6
SHEET_CELL_W = CELL + CELL_PAD * 2
SHEET_CELL_H = CELL + LABEL_HEIGHT + CELL_PAD


def checkerboard() -> Image.Image:
    image = Image.new("RGB", (CELL, CELL), "white")
    draw = ImageDraw.Draw(image)
    for y in range(0, CELL, TILE):
        for x in range(0, CELL, TILE):
            if (x // TILE + y // TILE) % 2:
                draw.rectangle((x, y, x + TILE - 1, y + TILE - 1), fill=(210, 210, 210))
    return image


def build_sheet(input_dir: Path, numbers: list[int], output: Path) -> None:
    sheet = Image.new("RGB", (SHEET_CELL_W * COLUMNS, SHEET_CELL_H * ROWS), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, number in enumerate(numbers):
        path = input_dir / f"{number:03d}.png"
        if not path.is_file():
            raise RuntimeError(f"missing runtime sprite for contact sheet: {path}")
        sprite = Image.open(path).convert("RGBA")
        if sprite.size != (CELL, CELL):
            raise RuntimeError(f"unexpected runtime sprite geometry for {path}: {sprite.size}")
        background = checkerboard().convert("RGBA")
        background.alpha_composite(sprite)
        col = index % COLUMNS
        row = index // COLUMNS
        x = col * SHEET_CELL_W + CELL_PAD
        y = row * SHEET_CELL_H + LABEL_HEIGHT
        sheet.paste(background.convert("RGB"), (x, y))
        draw.text((x, row * SHEET_CELL_H + 3), f"{number:03d}", fill="black", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--region", required=True)
    args = parser.parse_args()
    existing = sorted(int(path.stem) for path in args.input.glob("[0-9][0-9][0-9].png"))
    if not existing:
        raise SystemExit("no runtime sprites found")
    for page in range(4):
        start = page * 16 + 1
        requested = [n for n in range(start, start + 16) if n in existing]
        if not requested:
            continue
        build_sheet(
            args.input,
            requested,
            args.output / f"{args.region}-contact-{page + 1}.png",
        )
    print(f"contact sheets built for {args.region}: {len(existing)} sprites")


if __name__ == "__main__":
    main()
