import base64
import io
import unittest

from PIL import Image

from freeframe_worker import GenerationSpec, _png_payload


class GenerationSpecTests(unittest.TestCase):
    def test_valid_spec(self):
        GenerationSpec(prompt="plush guardian", width=512, height=512, steps=4).validate()

    def test_from_request_preserves_generation_identity(self):
        request = {
            "prompt": "plush guardian",
            "negative_prompt": "text, watermark",
            "width": 768,
            "height": 512,
            "steps": 12,
            "guidance_scale": 4.5,
            "seed": 1842,
        }
        spec = GenerationSpec.from_request(request)
        self.assertEqual(spec.prompt, request["prompt"])
        self.assertEqual(spec.negative_prompt, request["negative_prompt"])
        self.assertEqual(spec.width, 768)
        self.assertEqual(spec.height, 512)
        self.assertEqual(spec.steps, 12)
        self.assertEqual(spec.guidance_scale, 4.5)
        self.assertEqual(spec.seed, 1842)

    def test_empty_prompt_rejected(self):
        with self.assertRaises(ValueError):
            GenerationSpec(prompt="   ").validate()

    def test_bad_dimensions_rejected(self):
        for width, height in [(63, 512), (513, 512), (2048, 512)]:
            with self.subTest(width=width, height=height):
                with self.assertRaises(ValueError):
                    GenerationSpec(prompt="x", width=width, height=height).validate()

    def test_bad_steps_rejected(self):
        for steps in (0, 101):
            with self.assertRaises(ValueError):
                GenerationSpec(prompt="x", steps=steps).validate()

    def test_bad_guidance_rejected(self):
        for guidance in (-0.1, 30.1):
            with self.assertRaises(ValueError):
                GenerationSpec(prompt="x", guidance_scale=guidance).validate()

    def test_bad_seed_rejected(self):
        for seed in (-1, 2**63):
            with self.assertRaises(ValueError):
                GenerationSpec(prompt="x", seed=seed).validate()

    def test_png_payload_round_trip(self):
        image = Image.new("RGBA", (48, 32), (0, 0, 0, 0))
        payload = _png_payload(image)
        raw = base64.b64decode(payload["image_base64"])
        self.assertEqual(payload["mime_type"], "image/png")
        self.assertEqual(payload["width"], 48)
        self.assertEqual(payload["height"], 32)
        self.assertGreater(payload["bytes"], 0)
        with Image.open(io.BytesIO(raw)) as decoded:
            self.assertEqual(decoded.size, (48, 32))
            self.assertEqual(decoded.mode, "RGBA")


if __name__ == "__main__":
    unittest.main()
