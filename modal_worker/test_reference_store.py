import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from reference_store import load_reference_bytes, store_reference_bytes


class ReferenceStoreTests(unittest.TestCase):
    def _png(self, size=(96, 80)) -> bytes:
        out = io.BytesIO()
        Image.new("RGB", size, (120, 90, 60)).save(out, format="PNG")
        return out.getvalue()

    def test_store_is_content_addressed_and_reloadable(self):
        raw = self._png()
        with tempfile.TemporaryDirectory() as tmp:
            meta = store_reference_bytes(raw, tmp)
            self.assertEqual(len(meta.reference_id), 64)
            self.assertEqual(meta.reference_id, meta.sha256)
            self.assertEqual(meta.width, 96)
            self.assertEqual(meta.height, 80)
            self.assertEqual(load_reference_bytes(meta.reference_id, tmp), raw)
            # Idempotent re-store must preserve the same ID.
            again = store_reference_bytes(raw, tmp)
            self.assertEqual(again.reference_id, meta.reference_id)

    def test_bad_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_reference_bytes("../oops", tmp)

    def test_missing_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_reference_bytes("0" * 64, tmp)


if __name__ == "__main__":
    unittest.main()
