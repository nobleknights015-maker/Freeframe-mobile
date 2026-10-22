import unittest
from io import BytesIO

from PIL import Image

from mv_compositor import single_character_sheet
from png_compositor import compose_rgba_sheet, inspect_composite


def png_cell(width=16, height=24, alpha=255):
    image = Image.new("RGBA", (width, height), (120, 80, 40, alpha))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class PNGCompositorTests(unittest.TestCase):
    def test_composes_exact_transparent_sheet(self):
        spec = single_character_sheet(16, 24)
        result = compose_rgba_sheet(spec, [png_cell() for _ in range(12)])
        inspection = inspect_composite(result, spec)
        self.assertTrue(inspection["valid"])
        self.assertEqual((inspection["width"], inspection["height"]), (48, 96))
        self.assertTrue(inspection["has_alpha"])

    def test_wrong_cell_count_rejected(self):
        spec = single_character_sheet(16, 24)
        with self.assertRaisesRegex(ValueError, "expected 12 cells"):
            compose_rgba_sheet(spec, [png_cell() for _ in range(11)])

    def test_wrong_cell_dimensions_rejected_without_resizing(self):
        spec = single_character_sheet(16, 24)
        cells = [png_cell() for _ in range(12)]
        cells[5] = png_cell(17, 24)
        with self.assertRaisesRegex(ValueError, "cell size must be"):
            compose_rgba_sheet(spec, cells)

    def test_pixel_placement_is_deterministic(self):
        spec = single_character_sheet(2, 2)
        cells = []
        for index in range(12):
            image = Image.new("RGBA", (2, 2), (index, 0, 0, 255))
            output = BytesIO()
            image.save(output, format="PNG")
            cells.append(output.getvalue())
        result = compose_rgba_sheet(spec, cells)
        with Image.open(BytesIO(result)) as image:
            self.assertEqual(image.getpixel((0, 0))[0], 0)
            self.assertEqual(image.getpixel((2, 0))[0], 1)
            self.assertEqual(image.getpixel((0, 2))[0], 3)
            self.assertEqual(image.getpixel((4, 6))[0], 11)


if __name__ == "__main__":
    unittest.main()
