import unittest
from pathlib import Path


class ExtractionWorkerSurfaceTests(unittest.TestCase):
    def test_worker_defines_dedicated_extractor_and_bridge(self):
        source = Path(__file__).with_name("freeframe_worker.py").read_text(encoding="utf-8")
        self.assertIn("class FreeFrameExtractor", source)
        self.assertIn("def extract(self, request: dict)", source)
        self.assertIn("def extract_subject(request: dict)", source)
        self.assertIn("extract_and_validate(source, self.extractor)", source)

    def test_extractor_isolated_from_generator_class(self):
        source = Path(__file__).with_name("freeframe_worker.py").read_text(encoding="utf-8")
        generator_start = source.index("class FreeFrameGenerator")
        extractor_start = source.index("class FreeFrameExtractor")
        self.assertLess(generator_start, extractor_start)
        extractor_block = source[extractor_start:]
        self.assertIn('gpu="L4"', source[source.rfind("@app.cls", 0, extractor_start):extractor_start])
        self.assertIn("BiRefNetExtractor", extractor_block)


if __name__ == "__main__":
    unittest.main()
