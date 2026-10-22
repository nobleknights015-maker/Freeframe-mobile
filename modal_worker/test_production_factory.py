import unittest
from io import BytesIO

from PIL import Image

from production_factory import FACTORY_VERSION, build_faceset, build_single_character


def irregular_cell(width=31, height=43, inset=3):
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for x in range(inset, width - inset):
        for y in range(inset, height - inset):
            image.putpixel((x, y), (100, 120, 80, 255))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


class ProductionFactoryTests(unittest.TestCase):
    def test_irregular_sources_become_engine_valid_single_character(self):
        result = build_single_character([irregular_cell() for _ in range(12)])
        meta = result["metadata"]
        self.assertEqual(meta["factory_version"], FACTORY_VERSION)
        self.assertEqual(meta["profile"], "mv_single_character")
        self.assertEqual((meta["width"], meta["height"]), (144, 192))
        self.assertTrue(meta["engine_validation"]["valid"])
        self.assertEqual(meta["cell_count"], 12)
        self.assertEqual(len(meta["cell_transforms"]), 12)

    def test_faceset_pipeline_produces_exact_engine_dimensions(self):
        result = build_faceset([irregular_cell(101, 127) for _ in range(8)])
        meta = result["metadata"]
        self.assertEqual((meta["width"], meta["height"]), (576, 288))
        self.assertTrue(meta["engine_validation"]["valid"])
        self.assertEqual(meta["cell_count"], 8)

    def test_wrong_source_count_fails_before_packaging(self):
        with self.assertRaisesRegex(ValueError, "expected 12 source cells"):
            build_single_character([irregular_cell() for _ in range(11)])

    def test_every_transform_is_traceable(self):
        result = build_single_character([irregular_cell() for _ in range(12)])
        for index, transform in enumerate(result["metadata"]["cell_transforms"]):
            self.assertEqual(transform["cell_index"], index)
            self.assertEqual(transform["target_size"], [48, 48])
            self.assertEqual(transform["operation"], "rgba_contain_center")


if __name__ == "__main__":
    unittest.main()
