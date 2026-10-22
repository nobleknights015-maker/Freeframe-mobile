import unittest
from io import BytesIO

from PIL import Image

from image_normalizer import normalize_rgba_cell


def source_png(width=20, height=30):
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for x in range(5, width - 5):
        for y in range(5, height - 5):
            image.putpixel((x, y), (120, 90, 60, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class ImageNormalizerTests(unittest.TestCase):
    def test_exact_target_and_alpha(self):
        result, meta = normalize_rgba_cell(source_png(), target_width=48, target_height=48, padding=2)
        with Image.open(BytesIO(result)) as image:
            self.assertEqual(image.size, (48, 48))
            self.assertIn("A", image.getbands())
        self.assertEqual(meta["target_size"], [48, 48])
        self.assertEqual(meta["operation"], "rgba_contain_center")

    def test_aspect_ratio_is_preserved(self):
        _, meta = normalize_rgba_cell(source_png(20, 40), target_width=60, target_height=60)
        width, height = meta["resized_size"]
        self.assertEqual(width * 3, height)

    def test_transparent_margins_are_cropped(self):
        _, meta = normalize_rgba_cell(source_png(), target_width=48, target_height=48)
        self.assertEqual(meta["crop_box"], [5, 5, 15, 25])

    def test_fully_transparent_source_rejected(self):
        image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        output = BytesIO()
        image.save(output, format="PNG")
        with self.assertRaisesRegex(ValueError, "no visible pixels"):
            normalize_rgba_cell(output.getvalue(), target_width=48, target_height=48)

    def test_invalid_padding_rejected(self):
        with self.assertRaisesRegex(ValueError, "padding"):
            normalize_rgba_cell(source_png(), target_width=48, target_height=48, padding=24)


if __name__ == "__main__":
    unittest.main()
