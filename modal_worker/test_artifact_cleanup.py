import unittest
from io import BytesIO

from PIL import Image

from artifact_cleanup import alpha_bbox, crop_edge_band


def sample_png():
    image = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    for x in range(5, 15):
        for y in range(4, 16):
            image.putpixel((x, y), (100, 80, 60, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class ArtifactCleanupTests(unittest.TestCase):
    def test_alpha_bbox_finds_subject(self):
        self.assertEqual(alpha_bbox(sample_png()), (5, 4, 15, 16))

    def test_edge_crop_is_exact(self):
        cleaned = crop_edge_band(sample_png(), left=2, top=3, right=4, bottom=5)
        with Image.open(BytesIO(cleaned)) as image:
            self.assertEqual(image.size, (14, 12))
            self.assertIn("A", image.getbands())

    def test_invalid_crop_rejected(self):
        with self.assertRaisesRegex(ValueError, "entire image"):
            crop_edge_band(sample_png(), left=10, right=10)


if __name__ == "__main__":
    unittest.main()
