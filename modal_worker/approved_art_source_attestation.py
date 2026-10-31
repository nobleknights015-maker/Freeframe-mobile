"""Create and verify immutable SHA-256 attestations for Vera-approved source PNGs.

This module does not generate, resize, crop, convert, or repair artwork. It binds
one approval-ledger entry to the exact PNG bytes that were approved so a later
file replacement at the same path cannot inherit approval accidentally.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

SCHEMA = "plushbound.approved_source_attestation.v1"
PROVENANCE = "vera-chatgpt-approved"
APPROVAL_DESIGNATION = "VERA_APPROVED_SOURCE_V1"
TILE_SIZE = 48


def _load_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def _resolve_asset(round_manifest: Path, asset_id: str) -> tuple[dict[str, Any], Path]:
    round_manifest = round_manifest.resolve()
    data = _load_object(round_manifest)
    if data.get("schema") != "plushbound.approved_art_round.v1":
        raise ValueError("unsupported approved-art round schema")
    if data.get("provenance") != PROVENANCE:
        raise ValueError("approved-art round has invalid provenance")
    assets = data.get("assets")
    if not isinstance(assets, list):
        raise ValueError("approved-art round assets must be a list")
    matches = [row for row in assets if isinstance(row, dict) and row.get("asset_id") == asset_id]
    if len(matches) != 1:
        raise ValueError(f"asset must appear exactly once in approval ledger: {asset_id}")
    asset = matches[0]
    if asset.get("approval_status") != "approved":
        raise ValueError(f"{asset_id}: approval_status must be approved")
    if asset.get("approval_designation") != APPROVAL_DESIGNATION:
        raise ValueError(f"{asset_id}: invalid approval designation")
    if asset.get("production_authorized") is not True:
        raise ValueError(f"{asset_id}: production_authorized must be true")
    if asset.get("provenance", PROVENANCE) != PROVENANCE:
        raise ValueError(f"{asset_id}: invalid per-asset provenance")
    source_rel = asset.get("source_path")
    if not isinstance(source_rel, str) or not source_rel.lower().endswith(".png"):
        raise ValueError(f"{asset_id}: source_path must be a PNG")
    source = (round_manifest.parent / source_rel).resolve()
    root = round_manifest.parent.resolve()
    if root not in source.parents:
        raise ValueError(f"{asset_id}: source path escapes approved round root")
    return asset, source


def create_attestation(round_manifest: Path, asset_id: str) -> dict[str, Any]:
    asset, source = _resolve_asset(round_manifest, asset_id)
    if not source.is_file():
        raise FileNotFoundError(f"missing approved source PNG: {source}")
    raw = source.read_bytes()
    with Image.open(source) as image:
        image.load()
        if image.format != "PNG":
            raise ValueError(f"{asset_id}: source must be PNG")
        if image.mode not in {"RGB", "RGBA"}:
            raise ValueError(f"{asset_id}: source mode must be RGB or RGBA; got {image.mode}")
        footprint = asset.get("footprint_tiles")
        if footprint not in ([1, 1], [2, 2]):
            raise ValueError(f"{asset_id}: unsupported footprint")
        expected = (footprint[0] * TILE_SIZE, footprint[1] * TILE_SIZE)
        if image.size != expected:
            raise ValueError(
                f"{asset_id}: approved source size must be {expected[0]}x{expected[1]}; got {image.width}x{image.height}"
            )
        mode = image.mode
        size = list(image.size)
    return {
        "schema": SCHEMA,
        "asset_id": asset_id,
        "source_path": asset["source_path"],
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_size": size,
        "source_mode": mode,
        "footprint_tiles": asset["footprint_tiles"],
        "approval_status": "approved",
        "approval_designation": APPROVAL_DESIGNATION,
        "production_authorized": True,
        "provenance": PROVENANCE,
        "generator_used": False,
        "gpu_used": False,
        "pixels_modified": False,
    }


def verify_attestation(round_manifest: Path, attestation_path: Path) -> dict[str, Any]:
    attestation = _load_object(attestation_path.resolve())
    if attestation.get("schema") != SCHEMA:
        raise ValueError("unsupported approved-source attestation schema")
    asset_id = attestation.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id:
        raise ValueError("attestation asset_id must be non-empty")
    actual = create_attestation(round_manifest, asset_id)
    immutable_fields = (
        "asset_id", "source_path", "source_sha256", "source_size", "source_mode",
        "footprint_tiles", "approval_status", "approval_designation",
        "production_authorized", "provenance", "generator_used", "gpu_used",
        "pixels_modified",
    )
    mismatches = [field for field in immutable_fields if attestation.get(field) != actual.get(field)]
    if mismatches:
        raise ValueError(f"approved source attestation mismatch: {mismatches}")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round-manifest", type=Path, required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    try:
        if args.verify:
            result = verify_attestation(args.round_manifest, args.verify)
            result = {"status": "PASS", **result}
        else:
            result = create_attestation(args.round_manifest, args.asset_id)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            result = {"status": "ATTESTED", **result}
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
