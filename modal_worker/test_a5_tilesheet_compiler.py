from __future__ import annotations

import hashlib
import io
import unittest

from PIL import Image

from modal_worker.a5_tilesheet_compiler import (
    A5Slot,
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    SLOT_COUNT,
    TILE_SIZE,
    compile_a5,
)


class A5TilesheetCompilerTests(unittest.TestCase):
    @staticmethod
    def make_tile(slot: int, *, size=(TILE_SIZE, TILE_SIZE)) -> bytes:
        color = ((slot * 37) % 256, (slot * 67) % 256, (slot * 97) % 256, 255)
        image = Image.new("RGBA", size, color)
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()

    def test_exact_locked_geometry_and_hash(self):
        slots = [A5Slot(i, f"test.tile.{i:03d}", self.make_tile(i)) for i in range(SLOT_COUNT)]
        result = compile_a5(slots)
        raw = result["png"]
        meta = result["metadata"]

        self.assertEqual((meta["width"], meta["height"]), (CANVAS_WIDTH, CANVAS_HEIGHT))
        self.assertEqual((CANVAS_WIDTH, CANVAS_HEIGHT), (384, 768))
        self.assertEqual(meta["tile_width"], 48)
        self.assertEqual(meta["tile_height"], 48)
        self.assertEqual(meta["columns"], 8)
        self.assertEqual(meta["rows"], 16)
        self.assertEqual(meta["slot_count"], 128)
        self.assertEqual(meta["grid_origin"], [0, 0])
        self.assertEqual(meta["margins"], 0)
        self.assertEqual(meta["padding"], 0)
        self.assertFalse(meta["resized_after_generation"])
        self.assertFalse(meta["layout_inferred_visually"])
        self.assertFalse(meta["reference_sheet_pixels_used_as_runtime_art"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta["sha256"])

        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.size, (384, 768))
            slot = 127
            expected = ((slot * 37) % 256, (slot * 67) % 256, (slot * 97) % 256, 255)
            x = (slot % 8) * 48
            y = (slot // 8) * 48
            self.assertEqual(image.getpixel((x, y)), expected)
            self.assertEqual(image.getpixel((x + 47, y + 47)), expected)

    def test_wrong_sized_tile_fails_closed(self):
        slots = [A5Slot(i, f"test.tile.{i:03d}", self.make_tile(i)) for i in range(SLOT_COUNT)]
        slots[0] = A5Slot(0, "test.tile.bad", self.make_tile(0, size=(47, 48)))
        with self.assertRaisesRegex(ValueError, "exactly 48x48"):
            compile_a5(slots)

    def test_manifest_order_fails_closed(self):
        slots = [A5Slot(i, f"test.tile.{i:03d}", self.make_tile(i)) for i in range(SLOT_COUNT)]
        slots[0], slots[1] = slots[1], slots[0]
        with self.assertRaisesRegex(ValueError, "0..127"):
            compile_a5(slots)


if __name__ == "__main__":
    unittest.main()
