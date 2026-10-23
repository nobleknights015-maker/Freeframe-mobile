import unittest

from klein_l4_benchmark import MODEL_ID, select_case


class KleinL4BenchmarkTests(unittest.TestCase):
    def test_guardian_case_uses_klein_defaults(self):
        request = select_case("guardian_meadow")
        self.assertEqual(request["model_id"], MODEL_ID)
        self.assertEqual(request["model_candidate"], "flux2_klein_4b_candidate")
        self.assertEqual(request["steps"], 4)
        self.assertEqual(request["guidance_scale"], 1.0)
        self.assertEqual(request["width"] % 16, 0)
        self.assertEqual(request["height"] % 16, 0)

    def test_unknown_case_fails_closed(self):
        with self.assertRaises(ValueError):
            select_case("not-a-real-case")


if __name__ == "__main__":
    unittest.main()
