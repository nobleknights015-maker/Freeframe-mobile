import unittest
from io import BytesIO
from PIL import Image, ImageDraw

from extraction_provider import ExtractionError, ExtractionResult, extract_and_validate


def png_with_subject():
    image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((30, 15, 70, 85), fill=(120, 80, 50, 255))
    out = BytesIO(); image.save(out, format="PNG"); return out.getvalue()


class ExtractionProviderTests(unittest.TestCase):
    def test_valid_provider_output_passes_with_provenance(self):
        raw = png_with_subject()
        def extractor(_): return ExtractionResult(raw, "test-provider", "subject-v1")
        output, meta = extract_and_validate(b"source", extractor)
        self.assertEqual(output, raw)
        self.assertEqual(meta["extraction_provider"], "test-provider")
        self.assertEqual(meta["extraction_model"], "subject-v1")
        self.assertIn("foreground_fraction", meta["extraction_metrics"])

    def test_bad_alpha_output_is_rejected(self):
        opaque = BytesIO(); Image.new("RGBA", (100, 100), (1, 2, 3, 255)).save(opaque, format="PNG")
        with self.assertRaisesRegex(ExtractionError, "rejected"):
            extract_and_validate(b"source", lambda _: ExtractionResult(opaque.getvalue(), "p", "m"))

    def test_provider_failure_is_wrapped(self):
        def broken(_): raise RuntimeError("backend unavailable")
        with self.assertRaisesRegex(ExtractionError, "backend unavailable"):
            extract_and_validate(b"source", broken)

    def test_missing_provenance_and_empty_source_rejected(self):
        raw = png_with_subject()
        with self.assertRaises(ExtractionError): extract_and_validate(b"source", lambda _: ExtractionResult(raw, "", "m"))
        with self.assertRaises(ExtractionError): extract_and_validate(b"", lambda _: ExtractionResult(raw, "p", "m"))


if __name__ == "__main__":
    unittest.main()
