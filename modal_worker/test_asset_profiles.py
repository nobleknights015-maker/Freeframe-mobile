import unittest

from asset_profiles import validate_metadata


class AssetProfileTests(unittest.TestCase):
    def test_faceset_passes(self):
        result = validate_metadata(profile_name="mv_faceset", fmt="PNG", width=576, height=288, has_alpha=True)
        self.assertTrue(result["valid"])

    def test_faceset_wrong_size_fails(self):
        result = validate_metadata(profile_name="mv_faceset", fmt="PNG", width=512, height=288, has_alpha=True)
        self.assertFalse(result["valid"])
        self.assertIn("width must be 576", result["errors"])

    def test_regular_character_grid(self):
        self.assertTrue(validate_metadata(profile_name="mv_character_sheet", fmt="PNG", width=576, height=384, has_alpha=True)["valid"])
        self.assertFalse(validate_metadata(profile_name="mv_character_sheet", fmt="PNG", width=575, height=384, has_alpha=True)["valid"])

    def test_single_character_grid(self):
        self.assertTrue(validate_metadata(profile_name="mv_single_character", fmt="PNG", width=144, height=192, has_alpha=True)["valid"])

    def test_alpha_required(self):
        result = validate_metadata(profile_name="generic_rgba_png", fmt="PNG", width=64, height=64, has_alpha=False)
        self.assertFalse(result["valid"])

    def test_unknown_profile_fails_closed(self):
        result = validate_metadata(profile_name="made_up", fmt="PNG", width=64, height=64, has_alpha=True)
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
