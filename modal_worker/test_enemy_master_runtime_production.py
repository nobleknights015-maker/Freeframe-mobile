import hashlib
import io
import unittest

from PIL import Image, ImageDraw

from enemy_master_runtime_production import (
    MASTER_SIZE,
    TARGET_SIZE,
    MasterRecord,
    derive_one,
    expected_asset_ids,
    fit_static_battler,
    inspect_alpha,
    ledger_target_path,
    sha256_bytes,
)


def png_bytes(image):
    b = io.BytesIO()
    image.save(b, format="PNG")
    return b.getvalue()


def fake_source():
    im = Image.new("RGB", MASTER_SIZE, (80, 120, 160))
    return png_bytes(im)


def fake_extractor(source):
    im = Image.new("RGBA", MASTER_SIZE, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((200, 110, 820, 700), fill=(130, 190, 90, 255))
    return png_bytes(im), "birefnet", "ZhengPeng7/BiRefNet"


def record(asset_id="reg/elyndor/enemy-battle/001"):
    raw = fake_source()
    return raw, MasterRecord(
        asset_id,
        "masters/" + asset_id + ".png",
        sha256_bytes(raw),
        1024,
        768,
        "black-forest-labs/FLUX.2-klein-4B",
        "plushbound_enemy",
        "flux2_klein",
    )


class EnemyMasterRuntimeProductionTests(unittest.TestCase):
    def test_expected_id_contract(self):
        ids = expected_asset_ids()
        self.assertEqual(len(ids), 640)
        self.assertEqual(len(set(ids)), 640)
        self.assertEqual(ids[0], "reg/elyndor/enemy-battle/001")
        self.assertEqual(ids[-1], "reg/frostlace/enemy-battle/064")

    def test_fit_is_288_rgba_and_clear_edge(self):
        extracted = Image.open(io.BytesIO(fake_extractor(b"")[0])).convert("RGBA")
        out = fit_static_battler(extracted)
        gate = inspect_alpha(out)
        self.assertEqual(out.size, TARGET_SIZE)
        self.assertEqual(out.mode, "RGBA")
        self.assertTrue(gate["valid"])
        self.assertEqual(gate["edge_alpha_fraction"], 0)

    def test_derivation_is_byte_deterministic(self):
        raw, rec = record()
        a, ma = derive_one(rec, raw, fake_extractor)
        b, mb = derive_one(rec, raw, fake_extractor)
        self.assertEqual(a, b)
        self.assertEqual(ma, mb)
        self.assertEqual(ma["sha256"], hashlib.sha256(a).hexdigest())
        self.assertEqual((ma["width"], ma["height"], ma["mode"]), (288, 288, "RGBA"))

    def test_source_hash_mismatch_fails_closed(self):
        raw, rec = record()
        with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
            derive_one(rec, raw + b"x", fake_extractor)

    def test_wrong_extractor_provenance_fails_closed(self):
        raw, rec = record()

        def wrong(source):
            png, _, _ = fake_extractor(source)
            return png, "other", "model"

        with self.assertRaisesRegex(RuntimeError, "wrong extractor provenance"):
            derive_one(rec, raw, wrong)

    def test_ledger_target_mapping_is_exact(self):
        self.assertEqual(
            ledger_target_path("reg/elyndor/enemy-battle/001"),
            "game/assets/placeholders/regions/elyndor/enemy-battle/001.png",
        )


if __name__ == "__main__":
    unittest.main()
