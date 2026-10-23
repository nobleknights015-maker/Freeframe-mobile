import io
import unittest

from PIL import Image, ImageDraw

from composition_detector import inspect_panel_grid


def png_bytes(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class CompositionDetectorTests(unittest.TestCase):
    def test_detects_obvious_two_by_two_grid(self):
        image = Image.new("RGB", (512, 512), (220, 220, 220))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 255, 255), fill=(20, 180, 90))
        draw.rectangle((257, 0, 511, 255), fill=(180, 40, 40))
        draw.rectangle((0, 257, 255, 511), fill=(40, 80, 200))
        draw.rectangle((257, 257, 511, 511), fill=(220, 180, 40))
        draw.rectangle((253, 0, 259, 511), fill=(255, 255, 255))
        draw.rectangle((0, 253, 511, 259), fill=(255, 255, 255))
        result = inspect_panel_grid(png_bytes(image))
        self.assertTrue(result["panel_grid_detected"])

    def test_smooth_single_scene_not_detected(self):
        image = Image.new("RGB", (512, 512))
        pixels = image.load()
        for y in range(512):
            for x in range(512):
                pixels[x, y] = (80 + x // 8, 90 + y // 8, 120)
        result = inspect_panel_grid(png_bytes(image))
        self.assertFalse(result["panel_grid_detected"])

    def test_rejects_non_png(self):
        image = Image.new("RGB", (64, 64), (100, 100, 100))
        out = io.BytesIO(); image.save(out, format="JPEG")
        with self.assertRaises(ValueError):
            inspect_panel_grid(out.getvalue())


if __name__ == "__main__":
    unittest.main()
