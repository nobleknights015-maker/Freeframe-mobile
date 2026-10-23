import unittest

from extraction_backend_policy import NON_DEFAULT_BACKENDS, production_extraction_backend


class ExtractionBackendPolicyTests(unittest.TestCase):
    def test_birefnet_is_selected_with_canvas_preservation(self):
        policy = production_extraction_backend()
        self.assertEqual(policy.provider, "birefnet")
        self.assertEqual(policy.model, "ZhengPeng7/BiRefNet")
        self.assertEqual(policy.inference_size, 1024)
        self.assertTrue(policy.preserve_source_canvas)
        self.assertEqual(policy.output_mode, "rgba_cutout")
        self.assertEqual(policy.license_family, "MIT")

    def test_restricted_weight_backend_is_not_silently_selected(self):
        policy = production_extraction_backend()
        self.assertNotIn(policy.model, NON_DEFAULT_BACKENDS)
        self.assertIn("briaai/RMBG-2.0", NON_DEFAULT_BACKENDS)


if __name__ == "__main__":
    unittest.main()
