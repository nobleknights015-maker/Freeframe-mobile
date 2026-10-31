"""One-command production path for Plushbound WORLD_TILE_ASSET_V1.

Reads one locked world-tile manifest plus an approved source directory, resolves
only manifest-declared anchor PNGs beneath that root, compiles immutable source
bytes, exports the canonical production package, revalidates the exported
package, and emits one machine-readable PASS result. Any exception is a FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping

from modal_worker.a5_tilesheet_compiler import compile_world_tile_sheet, validate_world_tile_manifest
from modal_worker.world_tile_package_exporter import export_world_tile_package, validate_exported_package

RESULT_SCHEMA = "plushbound.world_tile_production_result.v1"


def _safe_source(root: Path, relative: str, asset_id: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError(f"{asset_id}: source_path must be a non-empty relative path")
    candidate = (root / relative).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"{asset_id}: source_path escapes approved source root")
    if not candidate.is_file():
        raise FileNotFoundError(f"{asset_id}: missing approved source PNG: {candidate}")
    return candidate


def _load_manifest(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("WORLD_TILE_ASSET_V1 manifest must be a JSON object")
    validate_world_tile_manifest(data)
    return data


def _load_declared_sources(manifest: Mapping[str, object], source_root: Path) -> dict[str, bytes]:
    slots = manifest.get("slots")
    if not isinstance(slots, list):
        raise ValueError("validated manifest slots unexpectedly missing")
    tile_pngs: dict[str, bytes] = {}
    for row in slots:
        if not isinstance(row, dict):
            continue
        asset_id = row.get("asset_id")
        source_path = row.get("source_path")
        if not isinstance(asset_id, str):
            continue
        if not isinstance(source_path, str):
            raise ValueError(f"{asset_id}: anchor source_path is missing")
        path = _safe_source(source_root, source_path, asset_id)
        tile_pngs[asset_id] = path.read_bytes()
    return tile_pngs


def run_production(
    manifest_path: Path,
    source_root: Path,
    output_root: Path,
    *,
    overwrite: bool = False,
) -> dict[str, object]:
    manifest_path = Path(manifest_path).resolve()
    source_root = Path(source_root).resolve()
    output_root = Path(output_root).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    if not source_root.is_dir():
        raise NotADirectoryError(f"approved source root not found: {source_root}")

    manifest = _load_manifest(manifest_path)
    tile_pngs = _load_declared_sources(manifest, source_root)
    compiled = compile_world_tile_sheet(manifest, tile_pngs)
    package_dir = export_world_tile_package(compiled, output_root, overwrite=overwrite)
    package_result = validate_exported_package(package_dir)

    return {
        "schema": RESULT_SCHEMA,
        "status": "PASS",
        "production_authorized": True,
        "sheet_id": manifest["sheet_id"],
        "material_id": manifest["material_id"],
        "declared_source_count": len(tile_pngs),
        "package_dir": str(package_dir),
        "package_status": package_result["status"],
        "runtime_import_proof": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile and export one approved WORLD_TILE_ASSET_V1 package")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        result = run_production(
            args.manifest,
            args.source_root,
            args.output_root,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        failure = {
            "schema": RESULT_SCHEMA,
            "status": "FAIL",
            "production_authorized": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "runtime_import_proof": False,
        }
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
