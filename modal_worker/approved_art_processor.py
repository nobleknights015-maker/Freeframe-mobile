from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path
from typing import Any

import modal

APP_NAME = "plushbound-approved-art-processor"
MAX_APPROVED_ASSETS_PER_RUN = 32
app = modal.App(APP_NAME)
image = modal.Image.debian_slim(python_version="3.11").pip_install("Pillow>=10.4,<12")


@app.function(image=image, cpu=1.0, memory=512, timeout=300)
def normalize_png(png_b64: str, target_size: int | None = None) -> dict[str, Any]:
    from PIL import Image

    raw = base64.b64decode(png_b64)
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
        if im.format != "PNG":
            raise ValueError("Approved source art must be PNG")
        if im.mode not in {"RGB", "RGBA"}:
            im = im.convert("RGBA")
        else:
            im = im.copy()

        source_size = [im.width, im.height]
        if target_size is not None:
            if target_size <= 0:
                raise ValueError("target_size must be positive")
            im = im.resize((target_size, target_size), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        im.save(out, format="PNG", optimize=False)
        payload = out.getvalue()

    return {
        "png_b64": base64.b64encode(payload).decode("ascii"),
        "source_size": source_size,
        "output_size": [target_size, target_size] if target_size else source_size,
        "mode": im.mode,
        "generator_used": False,
        "gpu_used": False,
    }


def _validate_manifest(data: dict[str, Any]) -> None:
    if data.get("schema") != "plushbound.approved_art_round.v1":
        raise ValueError("Unsupported manifest schema")
    if data.get("provenance") != "vera-chatgpt-approved":
        raise ValueError("Only Vera/ChatGPT-approved source art may enter this lane")
    if data.get("generator_calls_allowed") is not False:
        raise ValueError("Generator calls must be explicitly disabled")
    if data.get("gpu_allowed") is not False:
        raise ValueError("GPU use must be explicitly disabled")

    assets = data.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("Manifest assets must be a non-empty list")
    if len(assets) > MAX_APPROVED_ASSETS_PER_RUN:
        raise ValueError(
            f"Manifest contains {len(assets)} assets; hard cap is {MAX_APPROVED_ASSETS_PER_RUN}"
        )

    ids = [row.get("asset_id") for row in assets]
    if any(not isinstance(v, str) or not v for v in ids) or len(ids) != len(set(ids)):
        raise ValueError("asset_id values must be unique non-empty strings")


@app.local_entrypoint()
def main(manifest: str, output_dir: str = "approved-art-output") -> None:
    manifest_path = Path(manifest)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_manifest(data)

    root = manifest_path.parent
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema": "plushbound.approved_art_processing_report.v1",
        "round_id": data.get("round_id"),
        "generator_used": False,
        "gpu_used": False,
        "assets": [],
    }

    for row in data["assets"]:
        asset_id = row["asset_id"]
        source_path = (root / row["source_path"]).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Missing approved source art: {source_path}")

        target_size = row.get("target_size")
        raw = source_path.read_bytes()
        result = normalize_png.remote(base64.b64encode(raw).decode("ascii"), target_size)
        out_bytes = base64.b64decode(result.pop("png_b64"))
        output_name = row.get("output_name") or f"{asset_id}.png"
        output_path = out_root / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(out_bytes)

        report["assets"].append({
            "asset_id": asset_id,
            "source_path": str(source_path),
            "output_path": str(output_path),
            **result,
        })

    (out_root / "processing-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"APPROVED_ART_PROCESSING_COMPLETE={len(report['assets'])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", default="approved-art-output")
    args = parser.parse_args()
    main(manifest=args.manifest, output_dir=args.output_dir)
