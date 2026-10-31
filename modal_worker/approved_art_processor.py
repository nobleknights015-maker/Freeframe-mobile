from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from PIL import Image

MAX_APPROVED_ASSETS_PER_RUN = 32
TILE_SIZE = 48
ALLOWED_FOOTPRINTS = {(1, 1), (2, 2)}
APPROVAL_STATUS = "approved"
APPROVAL_DESIGNATION = "VERA_APPROVED_SOURCE_V1"
PROVENANCE = "vera-chatgpt-approved"


def _safe_child(root: Path, relative: str, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"{label} must be a non-empty relative path")
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"{label} escapes its authorized root: {relative}")
    return candidate


def _validate_manifest(data: dict[str, Any]) -> None:
    if data.get("schema") != "plushbound.approved_art_round.v1":
        raise ValueError("Unsupported manifest schema")
    if data.get("provenance") != PROVENANCE:
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

    ids: list[str] = []
    outputs: list[str] = []
    for row in assets:
        if not isinstance(row, dict):
            raise ValueError("Each asset entry must be an object")

        asset_id = row.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            raise ValueError("asset_id values must be non-empty strings")
        ids.append(asset_id)

        if row.get("approval_status") != APPROVAL_STATUS:
            raise ValueError(f"{asset_id}: approval_status must be '{APPROVAL_STATUS}'")
        if row.get("approval_designation") != APPROVAL_DESIGNATION:
            raise ValueError(
                f"{asset_id}: approval_designation must be '{APPROVAL_DESIGNATION}'"
            )
        if row.get("production_authorized") is not True:
            raise ValueError(f"{asset_id}: production_authorized must be true")
        if row.get("provenance", PROVENANCE) != PROVENANCE:
            raise ValueError(f"{asset_id}: invalid provenance")

        if "target_size" in row:
            raise ValueError(
                f"{asset_id}: target_size is forbidden; approved pixels may not be resized"
            )

        footprint = row.get("footprint_tiles")
        if (
            not isinstance(footprint, list)
            or len(footprint) != 2
            or not all(isinstance(v, int) for v in footprint)
            or tuple(footprint) not in ALLOWED_FOOTPRINTS
        ):
            raise ValueError(
                f"{asset_id}: footprint_tiles must be [1, 1] or [2, 2]"
            )

        source_path = row.get("source_path")
        if not isinstance(source_path, str) or not source_path.lower().endswith(".png"):
            raise ValueError(f"{asset_id}: source_path must point to a PNG")

        output_name = row.get("output_name") or f"{asset_id}.png"
        if not isinstance(output_name, str) or not output_name.lower().endswith(".png"):
            raise ValueError(f"{asset_id}: output_name must be a PNG path")
        outputs.append(output_name)

    if len(ids) != len(set(ids)):
        raise ValueError("asset_id values must be unique")
    if len(outputs) != len(set(outputs)):
        raise ValueError("output_name values must be unique")


def _inspect_approved_png(source_path: Path, footprint_tiles: list[int]) -> dict[str, Any]:
    raw = source_path.read_bytes()
    with Image.open(source_path) as im:
        im.load()
        if im.format != "PNG":
            raise ValueError(f"Approved source art must be PNG: {source_path}")
        if im.mode not in {"RGB", "RGBA"}:
            raise ValueError(
                f"Approved source art must already be RGB/RGBA; got {im.mode}: {source_path}"
            )

        expected = (footprint_tiles[0] * TILE_SIZE, footprint_tiles[1] * TILE_SIZE)
        actual = (im.width, im.height)
        if actual != expected:
            raise ValueError(
                f"Approved source dimensions {actual} do not match declared footprint "
                f"{footprint_tiles} -> {expected}: {source_path}"
            )

        mode = im.mode

    return {
        "size": list(actual),
        "footprint_tiles": footprint_tiles,
        "mode": mode,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "generator_used": False,
        "gpu_used": False,
        "pixels_resized": False,
    }


def process_manifest(manifest: str, output_dir: str = "approved-art-output") -> dict[str, Any]:
    manifest_path = Path(manifest).resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    _validate_manifest(data)

    root = manifest_path.parent.resolve()
    out_root = Path(output_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "schema": "plushbound.approved_art_processing_report.v2",
        "round_id": data.get("round_id"),
        "provenance": PROVENANCE,
        "execution_class": "local-cpu-deterministic-copy",
        "generator_used": False,
        "gpu_used": False,
        "pixels_resized": False,
        "assets": [],
    }

    for row in data["assets"]:
        asset_id = row["asset_id"]
        source_path = _safe_child(root, row["source_path"], "source_path")
        if not source_path.is_file():
            raise FileNotFoundError(f"Missing approved source art: {source_path}")

        result = _inspect_approved_png(source_path, row["footprint_tiles"])
        output_name = row.get("output_name") or f"{asset_id}.png"
        output_path = _safe_child(out_root, output_name, "output_name")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Preserve the exact approved PNG bytes. No conversion, cropping, scaling,
        # resampling, generation, or GPU processing is permitted in this lane.
        shutil.copyfile(source_path, output_path)
        output_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
        if output_sha256 != result["sha256"]:
            raise RuntimeError(f"Byte-for-byte copy verification failed: {asset_id}")

        report["assets"].append(
            {
                "asset_id": asset_id,
                "source_path": str(source_path),
                "output_path": str(output_path),
                "approval_status": row["approval_status"],
                "approval_designation": row["approval_designation"],
                "production_authorized": row["production_authorized"],
                **result,
            }
        )

    report_path = out_root / "processing-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"APPROVED_ART_PROCESSING_COMPLETE={len(report['assets'])}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", default="approved-art-output")
    args = parser.parse_args()
    process_manifest(manifest=args.manifest, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
