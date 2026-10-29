"""Zero-GPU deterministic self-test for the Plushbound A5 compiler."""
from __future__ import annotations

import hashlib
import io

from PIL import Image

from modal_worker.a5_tilesheet_compiler import (
    A5Slot,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    COLUMNS,
    ROWS,
    SLOT_COUNT,
    TILE_SIZE,
    compile_a5,
)


def make_tile(slot: int) -> bytes:
    # Deterministic synthetic runtime tile. Distinct RGB values make slot drift visible.
    r = (slot * 37) % 256
    g = (slot * 67) % 256
    b = (slot * 97) % 256
    image = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (r, g, b, 255))
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def main() -> None:
    slots = [A5Slot(slot=i, asset_id=f"test.tile.{i:03d}", png=make_tile(i)) for i in range(SLOT_COUNT)]
    result = compile_a5(slots)
    raw = result["png"]
    meta = result["metadata"]

    assert meta["width"] == CANVAS_WIDTH == 384
    assert meta["height"] == CANVAS_HEIGHT == 768
    assert meta["tile_width"] == meta["tile_height"] == TILE_SIZE == 48
    assert meta["columns"] == COLUMNS == 8
    assert meta["rows"] == ROWS == 16
    assert meta["slot_count"] == SLOT_COUNT == 128
    assert meta["grid_origin"] == [0, 0]
    assert meta["margins"] == 0 and meta["padding"] == 0
    assert meta["resized_after_generation"] is False
    assert meta["layout_inferred_visually"] is False
    assert meta["reference_sheet_pixels_used_as_runtime_art"] is False
    assert hashlib.sha256(raw).hexdigest() == meta["sha256"]

    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        assert image.format == "PNG"
        assert image.size == (384, 768)
        # Verify the final slot is at exact deterministic coordinates.
        slot = 127
        expected = ((slot * 37) % 256, (slot * 67) % 256, (slot * 97) % 256, 255)
        x = (slot % 8) * 48
        y = (slot // 8) * 48
        assert image.getpixel((x, y)) == expected
        assert image.getpixel((x + 47, y + 47)) == expected

    # Prove malformed geometry fails closed rather than resizing.
    bad = Image.new("RGBA", (47, 48), (1, 2, 3, 255))
    buf = io.BytesIO(); bad.save(buf, format="PNG")
    malformed = list(slots)
    malformed[0] = A5Slot(slot=0, asset_id="test.tile.bad", png=buf.getvalue())
    try:
        compile_a5(malformed)
    except ValueError as exc:
        assert "exactly 48x48" in str(exc)
    else:
        raise AssertionError("compiler resized or accepted malformed tile geometry")

    print("A5_TILE_SHEET_COMPILER_SELFTEST=PASS")
    print(meta["sha256"])


if __name__ == "__main__":
    main()
