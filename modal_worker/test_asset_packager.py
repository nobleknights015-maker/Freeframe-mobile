import unittest
from io import BytesIO

from PIL import Image

from asset_packager import package_faceset, package_single_character


def cell(width, height, value=100):
    image = Image.new("RGBA", (width, height), (value, 80, 40, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class AssetPackagerTests(unittest.TestCase):
    def test_single_character_is_engine_valid(self):
        result = package_single_character([cell(48, 48, i) for i in range(12)], cell_width=48, cell_height=48)
        meta = result["metadata"]
        self.assertEqual(meta["profile"], "mv_single_character")
        self.assertEqual(meta["filename_prefix"], "$")
        self.assertEqual((meta["width"], meta["height"]), (144, 192))
        self.assertTrue(meta["engine_validation"]["valid"])
        self.assertEqual(len(meta["sha256"]), 64)

    def test_faceset_is_exact_mv_size(self):
        result = package_faceset([cell(144, 144, i) for i in range(8)])
        meta = result["metadata"]
        self.assertEqual((meta["width"], meta["height"]), (576, 288))
        self.assertTrue(meta["engine_validation"]["valid"])

    def test_packager_refuses_bad_cells(self):
        cells = [cell(48, 48) for _ in range(12)]
        cells[7] = cell(47, 48)
        with self.assertRaisesRegex(ValueError, "cell size must be"):
            package_single_character(cells, cell_width=48, cell_height=48)


if __name__ == "__main__":
    unittest.main()
