"""Deterministic production exporter for WORLD_TILE_ASSET_V1 handoff packages.

The compiler remains geometry-only. This module owns filesystem serialization of
an already-compiled package and refuses to publish anything that does not pass
the canonical World Editor handoff gate.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Mapping

from modal_worker.world_editor_tile_ingest_gate import validate_world_editor_handoff

PACKAGE_SCHEMA = "plushbound.world_tile_export_package.v1"
PACKAGE_VERSION = "world-tile-export-v1"
PNG_NAME = "runtime.png"
MANIFEST_NAME = "manifest.json"
METADATA_NAME = "compiler-metadata.json"
HANDOFF_REPORT_NAME = "world-editor-handoff.json"
PACKAGE_INDEX_NAME = "package.json"
REQUIRED_FILES = (
    PNG_NAME,
    MANIFEST_NAME,
    METADATA_NAME,
    HANDOFF_REPORT_NAME,
    PACKAGE_INDEX_NAME,
)
_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def _canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _safe_component(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    cleaned = _SAFE_COMPONENT.sub("-", value.strip()).strip(".-")
    if not cleaned or cleaned in {".", ".."}:
        raise ValueError(f"{field} cannot produce an empty package path component")
    return cleaned


def build_package_index(
    manifest: Mapping[str, object],
    metadata: Mapping[str, object],
    handoff_report: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema": PACKAGE_SCHEMA,
        "package_version": PACKAGE_VERSION,
        "sheet_id": manifest["sheet_id"],
        "material_id": manifest["material_id"],
        "template_version": manifest["template_version"],
        "compiler_version": metadata["compiler_version"],
        "handoff_status": handoff_report["status"],
        "runtime_import_proof": False,
        "files": {
            "runtime_png": PNG_NAME,
            "manifest": MANIFEST_NAME,
            "compiler_metadata": METADATA_NAME,
            "world_editor_handoff_report": HANDOFF_REPORT_NAME,
        },
        "integrity": {
            "png_sha256": metadata["png_sha256"],
            "manifest_sha256": metadata["manifest_sha256"],
        },
    }


def export_world_tile_package(
    compiled: Mapping[str, object], output_root: Path, *, overwrite: bool = False
) -> Path:
    """Write one validated package atomically under output_root and return its directory."""
    png = compiled.get("png")
    manifest = compiled.get("manifest")
    metadata = compiled.get("metadata")
    if not isinstance(png, (bytes, bytearray)):
        raise ValueError("compiled package png must be bytes")
    if not isinstance(manifest, Mapping) or not isinstance(metadata, Mapping):
        raise ValueError("compiled package must contain manifest and metadata mappings")

    handoff_report = validate_world_editor_handoff(bytes(png), manifest, metadata)
    sheet_id = _safe_component(manifest.get("sheet_id"), "sheet_id")
    material_id = _safe_component(manifest.get("material_id"), "material_id")
    package_name = f"{material_id}__{sheet_id}"

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / package_name
    if destination.exists() and not overwrite:
        raise FileExistsError(f"production package already exists: {destination}")

    package_index = build_package_index(manifest, metadata, handoff_report)
    with tempfile.TemporaryDirectory(prefix=f".{package_name}.", dir=output_root) as temp_dir:
        staging = Path(temp_dir) / package_name
        staging.mkdir()
        (staging / PNG_NAME).write_bytes(bytes(png))
        (staging / MANIFEST_NAME).write_bytes(_canonical_json_bytes(manifest))
        (staging / METADATA_NAME).write_bytes(_canonical_json_bytes(metadata))
        (staging / HANDOFF_REPORT_NAME).write_bytes(_canonical_json_bytes(handoff_report))
        (staging / PACKAGE_INDEX_NAME).write_bytes(_canonical_json_bytes(package_index))

        validate_exported_package(staging)

        if destination.exists():
            if not overwrite:
                raise FileExistsError(f"production package already exists: {destination}")
            shutil.rmtree(destination)
        os.replace(staging, destination)

    return destination


def validate_exported_package(package_dir: Path) -> dict[str, object]:
    """Validate canonical names, package index, and the embedded handoff contract."""
    package_dir = Path(package_dir)
    if not package_dir.is_dir():
        raise ValueError(f"package directory is missing: {package_dir}")

    actual = {p.name for p in package_dir.iterdir() if p.is_file()}
    expected = set(REQUIRED_FILES)
    if actual != expected:
        raise ValueError(
            f"package must contain exactly {sorted(expected)}; found {sorted(actual)}"
        )

    manifest = json.loads((package_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    metadata = json.loads((package_dir / METADATA_NAME).read_text(encoding="utf-8"))
    report = json.loads((package_dir / HANDOFF_REPORT_NAME).read_text(encoding="utf-8"))
    index = json.loads((package_dir / PACKAGE_INDEX_NAME).read_text(encoding="utf-8"))
    if not all(isinstance(value, dict) for value in (manifest, metadata, report, index)):
        raise ValueError("all package JSON payloads must be objects")

    expected_report = validate_world_editor_handoff(
        (package_dir / PNG_NAME).read_bytes(), manifest, metadata
    )
    if report != expected_report:
        raise ValueError("embedded handoff report does not match canonical validation result")

    expected_index = build_package_index(manifest, metadata, expected_report)
    if index != expected_index:
        raise ValueError("package index does not match package contents")

    return {
        "schema": PACKAGE_SCHEMA,
        "status": "READY_FOR_WORLD_EDITOR_HANDOFF",
        "package_version": PACKAGE_VERSION,
        "package_dir": str(package_dir),
        "sheet_id": manifest["sheet_id"],
        "material_id": manifest["material_id"],
        "files": list(REQUIRED_FILES),
        "runtime_import_proof": False,
    }
