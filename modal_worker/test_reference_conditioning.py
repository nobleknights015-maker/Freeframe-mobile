import base64
import hashlib
import io
import unittest

from PIL import Image

from reference_conditioning import (
    DEFAULT_REFERENCE_SCALE,
    parse_reference_conditioning,
)


def _png(width=96, height=80):
    image = Image.new("RGB", (width, height), "white")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


class ReferenceConditioningTests(unittest.TestCase):
    def test_missing_reference_returns_none(self):
        self.assertIsNone(parse_reference_conditioning({}))

    def test_valid_reference_decodes_and_records_metadata(self):
        raw = _png()
        parsed = parse_reference_conditioning({
            "reference_image_base64": base64.b64encode(raw).decode("ascii")
        })
        self.assertEqual(parsed.width, 96)
        self.assertEqual(parsed.height, 80)
        self.assertEqual(parsed.scale, DEFAULT_REFERENCE_SCALE)
        self.assertEqual(len(parsed.sha256), 64)
        metadata = parsed.metadata()
        self.assertNotIn("image", metadata)
        self.assertEqual(metadata["width"], 96)
        self.assertIsNone(metadata["reference_id"])

    def test_cached_reference_resolves_by_sha(self):
        raw = _png()
        digest = hashlib.sha256(raw).hexdigest()
        parsed = parse_reference_conditioning(
            {"reference_id": digest, "reference_scale": 0.4},
            resolver=lambda reference_id: raw if reference_id == digest else b"",
        )
        self.assertEqual(parsed.reference_id, digest)
        self.assertEqual(parsed.sha256, digest)
        self.assertEqual(parsed.scale, 0.4)

    def test_cached_reference_without_resolver_is_rejected(self):
        raw = _png()
        digest = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):
            parse_reference_conditioning({"reference_id": digest})

    def test_custom_scale(self):
        raw = _png()
        parsed = parse_reference_conditioning({
            "reference_image_base64": base64.b64encode(raw).decode("ascii"),
            "reference_scale": 0.55,
        })
        self.assertEqual(parsed.scale, 0.55)

    def test_invalid_base64_rejected(self):
        with self.assertRaises(ValueError):
            parse_reference_conditioning({"reference_image_base64": "%%%"})

    def test_tiny_reference_rejected(self):
        raw = _png(32, 32)
        with self.assertRaises(ValueError):
            parse_reference_conditioning({
                "reference_image_base64": base64.b64encode(raw).decode("ascii")
            })

    def test_scale_out_of_range_rejected(self):
        raw = _png()
        with self.assertRaises(ValueError):
            parse_reference_conditioning({
                "reference_image_base64": base64.b64encode(raw).decode("ascii"),
                "reference_scale": 1.5,
            })


if __name__ == "__main__":
    unittest.main()
