import unittest

from mv_compositor import (
    MV_FACESET,
    placement_manifest,
    regular_character_sheet,
    single_character_sheet,
    validate_cells,
)


class MVCompositorTests(unittest.TestCase):
    def test_faceset_geometry(self):
        self.assertEqual((MV_FACESET.width, MV_FACESET.height), (576, 288))
        self.assertEqual(len(MV_FACESET.boxes()), 8)
        self.assertEqual(MV_FACESET.boxes()[0], (0, 0, 144, 144))
        self.assertEqual(MV_FACESET.boxes()[-1], (432, 144, 576, 288))

    def test_single_character_geometry(self):
        spec = single_character_sheet(48, 48)
        self.assertEqual((spec.width, spec.height), (144, 192))
        self.assertEqual(len(spec.boxes()), 12)

    def test_regular_character_geometry(self):
        spec = regular_character_sheet(48, 48)
        self.assertEqual((spec.width, spec.height), (576, 384))
        self.assertEqual(len(spec.boxes()), 96)

    def test_manifest_is_stable_row_major(self):
        spec = single_character_sheet(32, 48)
        names = [f"frame-{i}" for i in range(12)]
        manifest = placement_manifest(spec, names)
        self.assertEqual(manifest["placements"][0], {"name": "frame-0", "box": [0, 0, 32, 48]})
        self.assertEqual(manifest["placements"][3], {"name": "frame-3", "box": [0, 48, 32, 96]})
        self.assertEqual(manifest["placements"][-1]["box"], [64, 144, 96, 192])

    def test_wrong_cell_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "expected 12 cells"):
            validate_cells(single_character_sheet(48, 48), 11)

    def test_non_positive_cell_dimensions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            single_character_sheet(0, 48)


if __name__ == "__main__":
    unittest.main()
