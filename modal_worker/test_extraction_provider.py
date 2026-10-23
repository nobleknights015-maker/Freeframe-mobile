import unittest
from hashlib import sha256
from io import BytesIO
from PIL import Image, ImageDraw

from extraction_provider import ExtractionError, ExtractionResult, extract_and_validate


def png_with_subject(size=(100, 100)):
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle(
        (int(width * .3), int(height * .15), int(width * .7), int(height * .85)),
        fill=(120, 80, 50, 255),
    )
    out = BytesIO(); image.save(out, format="PNG"); return out.getvalue()


class ExtractionProviderTests(unittest.TestCase):
    def test_valid_provider_output_passes_with_provenance_dimensions_and_hashes(self):
        raw = png_with_subject()
        def extractor(_): return ExtractionResult(raw, "test-provider", "subject-v1")
        output, meta = extract_and_validate(raw, extractor)
        self.assertEqual(output, raw)
        self.assertEqual(meta["extraction_provider"], "test-provider")
        self.assertEqual(meta["extraction_model"], "subject-v1")
        self.assertEqual(meta["source_sha256"], sha256(raw).hexdigest())
        self.assertEqual(meta["output_sha256"], sha256(raw).hexdigest())
        self.assertEqual((meta["source_width"], meta["source_height"]), (100, 100))
        self.assertEqual((meta["output_width"], meta["output_height"]), (100, 100))
        self.assertIn("foreground_fraction", meta["extraction_metrics"])

    def test_bad_alpha_output_is_rejected(self):
        raw = png_with_subject()
        opaque = BytesIO(); Image.new("RGBA", (100, 100), (1, 2, 3, 255)).save(opaque, format="PNG")
        with self.assertRaisesRegex(ExtractionError, "rejected"):
            extract_and_validate(raw, lambda _: ExtractionResult(opaque.getvalue(), "p", "m"))

    def test_dimension_change_is_rejected(self):
        source = png_with_subject((100, 100))
        resized = png_with_subject((80, 100))
        with self.assertRaisesRegex(ExtractionError, "dimensions changed"):
            extract_and_validate(source, lambda _: ExtractionResult(resized, "p", "m"))

    def test_non_png_source_and_output_are_rejected(self):
        raw = png_with_subject()
        jpeg = BytesIO(); Image.new("RGB", (100, 100), (1, 2, 3)).save(jpeg, format="JPEG")
        with self.assertRaisesRegex(ExtractionError, "source must be PNG"):
            extract_and_validate(jpeg.getvalue(), lambda _: ExtractionResult(raw, "p", "m"))
        with self.assertRaisesRegex(ExtractionError, "extracted output must be PNG"):
            extract_and_validate(raw, lambda _: ExtractionResult(jpeg.getvalue(), "p", "m"))

    def test_provider_failure_is_wrapped(self):
        raw = png_with_subject()
        def broken(_): raise RuntimeError("backend unavailable")
        with self.assertRaisesRegex(ExtractionError, "backend unavailable"):
            extract_and_validate(raw, broken)

    def test_missing_provenance_empty_output_and_empty_source_rejected(self):
        raw = png_with_subject()
        with self.assertRaises(ExtractionError): extract_and_validate(raw, lambda _: ExtractionResult(raw, "", "m"))
        with self.assertRaisesRegex(ExtractionError, "empty PNG"):
            extract_and_validate(raw, lambda _: ExtractionResult(b"", "p", "m"))
        with self.assertRaises(ExtractionError): extract_and_validate(b"", lambda _: ExtractionResult(raw, "p", "m"))


if __name__ == "__main__":
    unittest.main()
