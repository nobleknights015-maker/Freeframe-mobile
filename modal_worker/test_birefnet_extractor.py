import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from birefnet_extractor import BiRefNetExtractor
from extraction_provider import ExtractionError, extract_and_validate


def source_png(size=(80, 120)):
    out = BytesIO()
    Image.new("RGB", size, (80, 120, 160)).save(out, format="PNG")
    return out.getvalue()


class FakeBiRefNetExtractor(BiRefNetExtractor):
    def __init__(self):
        super().__init__(model=object(), torch_module=object())

    def _predict_mask(self, image):
        mask = Image.new("L", image.size, 0)
        # centered foreground that satisfies the alpha quality gate
        for x in range(image.width // 4, image.width * 3 // 4):
            for y in range(image.height // 8, image.height * 7 // 8):
                mask.putpixel((x, y), 255)
        return mask


class BiRefNetExtractorTests(unittest.TestCase):
    def test_adapter_preserves_canvas_and_passes_contract(self):
        raw = source_png()
        output, meta = extract_and_validate(raw, FakeBiRefNetExtractor())
        with Image.open(BytesIO(output)) as image:
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.size, (80, 120))
            self.assertNotEqual(image.getchannel("A").getextrema(), (255, 255))
        self.assertEqual(meta["extraction_provider"], "birefnet")
        self.assertEqual(meta["extraction_model"], "ZhengPeng7/BiRefNet")
        self.assertEqual((meta["source_width"], meta["source_height"]), (80, 120))
        self.assertEqual((meta["output_width"], meta["output_height"]), (80, 120))

    def test_non_png_input_is_rejected(self):
        jpeg = BytesIO(); Image.new("RGB", (80, 120)).save(jpeg, format="JPEG")
        with self.assertRaisesRegex(ExtractionError, "must be PNG"):
            FakeBiRefNetExtractor()(jpeg.getvalue())

    def test_missing_heavy_dependencies_has_clear_error(self):
        with patch.dict("sys.modules", {"torch": None, "transformers": None}):
            with self.assertRaisesRegex(ExtractionError, "requires torch and transformers"):
                BiRefNetExtractor()


if __name__ == "__main__":
    unittest.main()
