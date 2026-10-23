import unittest
from io import BytesIO
from PIL import Image, ImageDraw

from alpha_extraction_gate import inspect_extracted_png


def png_with_box(size=(200, 200), box=(50, 30, 150, 190)):
    image = Image.new("RGBA", size, (0, 0, 0, 0)); draw = ImageDraw.Draw(image); draw.rectangle(box, fill=(120, 80, 60, 255))
    out = BytesIO(); image.save(out, format="PNG"); return out.getvalue()


class AlphaExtractionGateTests(unittest.TestCase):
    def test_clean_isolated_subject_passes(self):
        result = inspect_extracted_png(png_with_box())
        self.assertTrue(result["accepted"])
        self.assertGreater(result["foreground_fraction"], 0.03)
        self.assertEqual(result["edge_alpha_fraction"], 0.0)

    def test_fully_opaque_scene_fails(self):
        image = Image.new("RGBA", (100, 100), (10, 20, 30, 255)); out = BytesIO(); image.save(out, format="PNG")
        result = inspect_extracted_png(out.getvalue())
        self.assertFalse(result["accepted"])
        self.assertTrue(any("too much opaque" in x for x in result["errors"]))

    def test_empty_alpha_fails(self):
        image = Image.new("RGBA", (100, 100), (0, 0, 0, 0)); out = BytesIO(); image.save(out, format="PNG")
        result = inspect_extracted_png(out.getvalue())
        self.assertFalse(result["accepted"])
        self.assertTrue(any("no foreground" in x for x in result["errors"]))

    def test_tiny_fragment_fails(self):
        result = inspect_extracted_png(png_with_box(box=(95, 95, 100, 100)))
        self.assertFalse(result["accepted"])

    def test_edge_contamination_fails(self):
        result = inspect_extracted_png(png_with_box(box=(0, 0, 199, 80)))
        self.assertFalse(result["accepted"])
        self.assertTrue(any("canvas edge" in x for x in result["errors"]))

    def test_invalid_bytes_fail_cleanly(self):
        result = inspect_extracted_png(b"not an image")
        self.assertFalse(result["accepted"])
        self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
