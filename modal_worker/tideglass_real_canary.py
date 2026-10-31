"""Fail-closed real Tideglass production canary.

This canary may only use a named Vera-approved source from the real approved-art
round ledger. It refuses synthetic/test/fixture substitution. If the real source
bytes are absent, it reports BLOCKED rather than manufacturing a green proof.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from modal_worker.world_tile_production_cli import run_production

CANARY_SCHEMA = "plushbound.real_production_canary_result.v1"
FORBIDDEN_SOURCE_MARKERS = ("fixture", "synthetic", "tests/", "test/")


def _load_object(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path}")
    return data


def _slot(index: int, *, role: str = "empty", asset_id: str | None = None,
          source_path: str | None = None, covered_by: str | None = None,
          footprint: list[int] | None = None) -> dict[str, object]:
    row = index // 8
    column = index % 8
    entry: dict[str, object] = {
        "slot_index": index,
        "row": row,
        "column": column,
        "x": column * 48,
        "y": row * 48,
        "role": role,
        "asset_id": asset_id,
        "source_path": source_path,
    }
    if covered_by is not None:
        entry["covered_by"] = covered_by
    if footprint is not None:
        entry["footprint_tiles"] = footprint
    return entry


def _build_world_manifest(asset: dict[str, object], source_name: str) -> dict[str, object]:
    asset_id = str(asset["asset_id"])
    footprint = asset["footprint_tiles"]
    slots = [_slot(i) for i in range(128)]
    slots[0] = _slot(0, role="a1_floor", asset_id=asset_id, source_path=source_name, footprint=footprint)
    slots[0].update({
        "approval_status": asset["approval_status"],
        "approval_designation": asset["approval_designation"],
        "production_authorized": asset["production_authorized"],
        "provenance": asset.get("provenance", "vera-chatgpt-approved"),
    })
    for index in (1, 8, 9):
        slots[index] = _slot(index, role="a1_floor", covered_by=asset_id)
    return {
        "schema": "plushbound.world_tile_sheet.v1",
        "template_version": "WORLD_TILE_ASSET_V1",
        "sheet_id": "tideglass-real-canary-001",
        "material_id": asset_id,
        "canvas_width": 384,
        "canvas_height": 768,
        "tile_size": 48,
        "columns": 8,
        "rows": 16,
        "provenance": "vera-chatgpt-approved",
        "generator_calls_allowed": False,
        "gpu_allowed": False,
        "slots": slots,
    }


def run_canary(config_path: Path, output_root: Path) -> dict[str, object]:
    config_path = config_path.resolve()
    repo_root = config_path.parents[2]
    config = _load_object(config_path)
    round_path = (repo_root / str(config["round_manifest"])).resolve()
    round_data = _load_object(round_path)
    if round_data.get("schema") != "plushbound.approved_art_round.v1":
        raise ValueError("canary round manifest has unsupported schema")
    if round_data.get("provenance") != "vera-chatgpt-approved":
        raise ValueError("canary round lacks required Vera provenance")

    asset_id = str(config["asset_id"])
    assets = round_data.get("assets")
    if not isinstance(assets, list):
        raise ValueError("canary round assets must be a list")
    matches = [row for row in assets if isinstance(row, dict) and row.get("asset_id") == asset_id]
    if len(matches) != 1:
        raise ValueError(f"canary asset must appear exactly once in approval ledger: {asset_id}")
    asset = matches[0]

    if asset.get("approval_status") != "approved" or asset.get("approval_designation") != "VERA_APPROVED_SOURCE_V1":
        raise ValueError("canary asset is not explicitly Vera-approved")
    if asset.get("production_authorized") is not True:
        raise ValueError("canary asset is not production-authorized")
    if asset.get("footprint_tiles") != config.get("expected_footprint_tiles"):
        raise ValueError("canary footprint differs from locked expectation")
    source_rel = asset.get("source_path")
    if source_rel != config.get("expected_source_path") or not isinstance(source_rel, str):
        raise ValueError("canary source path differs from locked expectation")
    lowered = source_rel.lower().replace("\\", "/")
    if any(marker in lowered for marker in FORBIDDEN_SOURCE_MARKERS):
        raise ValueError("synthetic/test/fixture source substitution is forbidden")

    source_path = (round_path.parent / source_rel).resolve()
    round_root = round_path.parent.resolve()
    if round_root not in source_path.parents:
        raise ValueError("canary source escapes approved round root")
    if not source_path.is_file():
        return {
            "schema": CANARY_SCHEMA,
            "status": "BLOCKED_MISSING_REAL_APPROVED_ASSET",
            "production_authorized": False,
            "asset_id": asset_id,
            "expected_source": str(source_path.relative_to(repo_root)),
            "synthetic_substitution_used": False,
            "runtime_import_proof": False,
        }

    source_root = source_path.parent
    with tempfile.TemporaryDirectory(prefix="tideglass-real-canary-manifest-") as temp_dir:
        manifest_path = Path(temp_dir) / "manifest.json"
        manifest = _build_world_manifest(asset, source_path.name)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        result = run_production(manifest_path, source_root, output_root, overwrite=True)

    return {
        "schema": CANARY_SCHEMA,
        "status": "PASS_REAL_APPROVED_TIDEGLASS_CANARY",
        "production_authorized": True,
        "asset_id": asset_id,
        "source": str(source_path.relative_to(repo_root)),
        "synthetic_substitution_used": False,
        "package_dir": result["package_dir"],
        "package_status": result["package_status"],
        "runtime_import_proof": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--contract-check", action="store_true", help="BLOCKED is an expected non-failure while real bytes are absent")
    args = parser.parse_args()
    try:
        result = run_canary(args.config, args.output_root)
    except Exception as exc:
        print(json.dumps({
            "schema": CANARY_SCHEMA,
            "status": "FAIL",
            "production_authorized": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "runtime_import_proof": False,
        }, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    if result["status"] == "BLOCKED_MISSING_REAL_APPROVED_ASSET":
        return 0 if args.contract_check else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
