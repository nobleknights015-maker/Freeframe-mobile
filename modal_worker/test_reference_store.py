import hashlib
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

    def test_expected_integrity_accepts_complete_payload(self):
        raw = self._png()
        expected_sha256 = hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            meta = store_reference_bytes(
                raw,
                tmp,
                expected_sha256=expected_sha256,
                expected_bytes=len(raw),
            )
            self.assertEqual(meta.sha256, expected_sha256)
            self.assertEqual(meta.bytes, len(raw))

    def test_truncated_raster_is_rejected_without_artifact(self):
        raw = self._png()
        truncated = raw[: len(raw) // 2]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "readable raster image"):
                store_reference_bytes(truncated, tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_checksum_mismatch_is_rejected_without_artifact(self):
        raw = self._png()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                store_reference_bytes(raw, tmp, expected_sha256="0" * 64)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_byte_count_mismatch_is_rejected_without_artifact(self):
        raw = self._png()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "byte count mismatch"):
                store_reference_bytes(raw, tmp, expected_bytes=len(raw) + 1)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_corrupted_cached_file_is_repaired_by_valid_resubmission(self):
        raw = self._png()
        with tempfile.TemporaryDirectory() as tmp:
            meta = store_reference_bytes(raw, tmp)
            cached = Path(tmp) / meta.reference_id
            cached.write_bytes(b"corrupt")
            repaired = store_reference_bytes(
                raw,
                tmp,
                expected_sha256=meta.sha256,
                expected_bytes=len(raw),
            )
            self.assertEqual(repaired.reference_id, meta.reference_id)
            self.assertEqual(load_reference_bytes(meta.reference_id, tmp), raw)

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
