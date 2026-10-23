"""Run BiRefNet extraction against current Klein rehearsal subject outputs."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import modal

APP_NAME = "freeframe-current-extraction-smoke"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "pillow>=10.4,<12",
        "torch>=2.6,<3",
        "transformers",
        "safetensors",
    )
    .add_local_python_source("modal_worker")
)
app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=60, timeout=900)
class CurrentExtractorSmoke:
    @modal.enter()
    def load(self):
        import os
        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        from modal_worker.birefnet_extractor import BiRefNetExtractor
        self.extractor = BiRefNetExtractor()

    @modal.method()
    def extract(self, source_png: bytes) -> dict:
        from modal_worker.extraction_provider import extract_and_validate
        output_png, metadata = extract_and_validate(source_png, self.extractor)
        return {
            "png_base64": base64.b64encode(output_png).decode("ascii"),
            "metadata": metadata,
        }


@app.local_entrypoint()
def main(character_path: str, guardian_path: str, enemy_path: str):
    paths = {
        "character": Path(character_path),
        "guardian": Path(guardian_path),
        "enemy": Path(enemy_path),
    }
    output_dir = Path("current-extraction-smoke")
    output_dir.mkdir(exist_ok=True)
    report = {"version": "current-klein-extraction-smoke-v1", "assets": []}
    runner = CurrentExtractorSmoke()
    for category, path in paths.items():
        source = path.read_bytes()
        result = runner.extract.remote(source)
        output = base64.b64decode(result.pop("png_base64"))
        output_path = output_dir / f"{category}-extracted.png"
        output_path.write_bytes(output)
        report["assets"].append({
            "category": category,
            "source_path": str(path),
            "output_path": str(output_path),
            "metadata": result["metadata"],
        })
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
