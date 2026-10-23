import unittest

from extraction_routing import (
    EXTRACTION_BYPASS_CLASSES,
    EXTRACTION_REQUIRED_CLASSES,
    extraction_route,
    requires_subject_extraction,
)


class ExtractionRoutingTests(unittest.TestCase):
    def test_subject_classes_require_extraction(self):
        expected = {
            "character_master",
            "guardian_master",
            "enemy_master",
            "portrait_master",
            "icon_master",
        }
        self.assertEqual(EXTRACTION_REQUIRED_CLASSES, expected)
        for asset_class in expected:
            with self.subTest(asset_class=asset_class):
                self.assertTrue(requires_subject_extraction(asset_class))
                self.assertEqual(extraction_route(asset_class), "extract_subject")

    def test_scene_and_composite_classes_bypass_extraction(self):
        expected = {"environment_master", "sprite_master", "tileset_master"}
        self.assertEqual(EXTRACTION_BYPASS_CLASSES, expected)
        for asset_class in expected:
            with self.subTest(asset_class=asset_class):
                self.assertFalse(requires_subject_extraction(asset_class))
                self.assertEqual(extraction_route(asset_class), "bypass")

    def test_unknown_or_empty_class_fails_closed(self):
        for value in ("", "   ", "future_master", None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    requires_subject_extraction(value)


if __name__ == "__main__":
    unittest.main()
