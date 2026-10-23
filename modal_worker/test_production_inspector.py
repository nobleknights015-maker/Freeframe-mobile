import base64
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from batch_executor import run_batch
from batch_state import stable_asset_id
from production_inspector import asset_class_for_item, inspect_generation


def encode_png(image: Image.Image) -> str:
    out = io.BytesIO(); image.save(out, format="PNG")
    return base64.b64encode(out.getvalue()).decode("ascii")


def grid_payload() -> dict:
    image = Image.new("RGB", (512, 512), (220, 220, 220))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 255, 255), fill=(20, 180, 90))
    draw.rectangle((257, 0, 511, 255), fill=(180, 40, 40))
    draw.rectangle((0, 257, 255, 511), fill=(40, 80, 200))
    draw.rectangle((257, 257, 511, 511), fill=(220, 180, 40))
    draw.rectangle((253, 0, 259, 511), fill=(255, 255, 255))
    draw.rectangle((0, 253, 511, 259), fill=(255, 255, 255))
    return {"image_base64": encode_png(image)}


def scene_payload() -> dict:
    image = Image.new("RGB", (512, 512))
    pixels = image.load()
    for y in range(512):
        for x in range(512):
            pixels[x, y] = (70 + x // 8, 90 + y // 8, 120)
    return {"image_base64": encode_png(image)}


class ProductionInspectorTests(unittest.TestCase):
    def test_preset_maps_to_asset_class(self):
        self.assertEqual(asset_class_for_item({"preset": "plushbound_guardian"}), "guardian_master")

    def test_grid_is_rejected(self):
        result = inspect_generation({"preset": "plushbound_guardian"}, grid_payload())
        self.assertFalse(result["accepted"])
        self.assertTrue(result["composition_detector"]["panel_grid_detected"])
        self.assertIn("multi-panel or model-sheet composition detected", result["errors"])

    def test_single_scene_is_accepted(self):
        result = inspect_generation({"preset": "plushbound_guardian"}, scene_payload())
        self.assertTrue(result["accepted"])
        self.assertFalse(result["composition_detector"]["panel_grid_detected"])

    def test_batch_retries_after_grid_rejection(self):
        item = {
            "path": "masters/guardian.png",
            "prompt": "small riverotter plush guardian",
            "profile": "guardian_master",
            "preset": "plushbound_guardian",
            "seed": 4404,
        }
        calls = {"count": 0}

        def generate(request):
            calls["count"] += 1
            payload = grid_payload() if calls["count"] == 1 else scene_payload()
            return {**payload, "seed": request["seed"]}

        with tempfile.TemporaryDirectory() as tmp:
            state = run_batch(
                [item],
                Path(tmp) / "state.json",
                "panel-retry",
                generate,
                inspect=inspect_generation,
                max_attempts=2,
            )
            asset_id = stable_asset_id(item["path"], item["prompt"], item["profile"])
            self.assertIn(asset_id, state.completed)
            self.assertEqual(calls["count"], 2)
            self.assertEqual(state.completed[asset_id]["retry_attempt"], 2)
            self.assertNotIn(asset_id, state.failed)


if __name__ == "__main__":
    unittest.main()
