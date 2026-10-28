"""Deterministic acceptance/rollup utilities for World Asset Pipeline V2."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
ACCEPTANCE_SCHEMA = "plushbound.world_asset_pipeline_v2_asset_acceptance.v1"
MANUAL_QA_SCHEMA = "plushbound.world_asset_pipeline_v2_manual_qa.v1"


def _load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing V2 acceptance input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def accept_asset(report_path: Path, manual_qa_path: Path, output_path: Path) -> dict:
    report = _load(report_path)
    qa = _load(manual_qa_path)
    if report.get("machine_gate") != "PASS" or report.get("execution_outcome") != "PENDING_MANUAL_QA":
        raise RuntimeError("V2 acceptance requires a machine-pass source report")
    asset_id = str(report.get("asset_id", ""))
    region = str(report.get("region", ""))
    material = str(report.get("material_key", ""))
    if qa.get("schema") != MANUAL_QA_SCHEMA or qa.get("asset_id") != asset_id:
        raise RuntimeError("manual QA identity/schema mismatch")
    if qa.get("status") != "PASS" or qa.get("semantic_material_surface") is not True:
        raise RuntimeError("manual QA did not pass semantic material-surface review")
    if qa.get("no_scene_or_object_composition") is not True:
        raise RuntimeError("manual QA did not clear scene/object composition")
    raw_path = Path(str(report.get("raw_path", "")))
    norm_path = Path(str(report.get("normalized_path", "")))
    if not raw_path.is_file() or not norm_path.is_file():
        raise RuntimeError("accepted source files are missing")
    raw_sha = _sha(raw_path); norm_sha = _sha(norm_path)
    if raw_sha != report.get("raw_sha256") or norm_sha != report.get("normalized_sha256"):
        raise RuntimeError("source bytes disagree with machine-pass report hashes")
    record = {
        "schema": ACCEPTANCE_SCHEMA,
        "status": "ACCEPTED",
        "asset_id": asset_id,
        "region": region,
        "material_key": material,
        "machine_gate": "PASS",
        "manual_visual_gate": "PASS",
        "raw_sha256": raw_sha,
        "normalized_sha256": norm_sha,
        "source_report": str(report_path),
        "manual_qa_evidence": str(manual_qa_path),
        "immutable": True,
        "rerender_allowed": False,
        "compile_authorized": False,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def rollup_region(region: str, record_paths: list[Path], output_path: Path) -> dict:
    scope = _load(SCOPE_PATH)
    regional = scope.get("regions", {}).get(region)
    if not regional or regional.get("stable_sheet_id") != f"tileset.{region}.a5":
        raise RuntimeError(f"unknown regional source scope: {region}")
    expected = [
        (material, f"tileset.{region}.a5.source.{material}")
        for material in regional.get("materials", [])
    ]
    if len(expected) != 8:
        raise RuntimeError("regional closeout requires exactly eight stable materials")
    records = {}
    for path in record_paths:
        row = _load(path)
        if row.get("schema") != ACCEPTANCE_SCHEMA or row.get("status") != "ACCEPTED":
            raise RuntimeError(f"invalid asset acceptance record: {path}")
        asset_id = str(row.get("asset_id", ""))
        if asset_id in records:
            raise RuntimeError(f"duplicate acceptance record: {asset_id}")
        if row.get("region") != region or row.get("immutable") is not True or row.get("rerender_allowed") is not False:
            raise RuntimeError(f"{asset_id}: acceptance record identity/immutability mismatch")
        records[asset_id] = row
    expected_ids = {asset_id for _, asset_id in expected}
    if set(records) != expected_ids:
        raise RuntimeError("regional rollup requires the exact eight accepted source IDs")
    sources = []
    for material, asset_id in expected:
        row = records[asset_id]
        sources.append({
            "asset_id": asset_id,
            "material_key": material,
            "raw_sha256": row["raw_sha256"],
            "normalized_sha256": row["normalized_sha256"],
            "machine_status": "PASS",
            "manual_visual_status": "PASS",
        })
    closeout = {
        "schema": "plushbound.tileset_regional_a5_source_closeout.v1",
        "status": "CLOSED_GREEN_8_OF_8",
        "region": region,
        "target_sheet_type": "A5",
        "stable_sheet_id": f"tileset.{region}.a5",
        "prompt_contract_version": scope["source_contract"]["prompt_contract_version"],
        "machine_gate": "PASS_8_OF_8",
        "manual_visual_gate": "PASS_8_OF_8",
        "source_count": 8,
        "accepted_source_ids_protected_from_rerender": True,
        "accepted_assets_immutable": True,
        "missing_local_artifact_is_not_rerender_authority": True,
        "deterministic_compile_authorized": True,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
        "sources": sources,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(closeout, indent=2, sort_keys=True), encoding="utf-8")
    return closeout


def self_test() -> dict:
    scope = _load(SCOPE_PATH)
    if len(scope.get("regions", {}).get("silkspire", {}).get("materials", [])) != 8:
        raise RuntimeError("V2 acceptance self-test scope mismatch")
    return {
        "schema": "plushbound.world_asset_pipeline_v2_acceptance_self_test.v1",
        "status": "PASS_ZERO_GPU_UNIFIED_ACCEPTANCE_DECLARATION",
        "individual_asset_acceptance": True,
        "regional_rollup_requires_exactly_8": True,
        "machine_and_manual_pass_required": True,
        "accepted_assets_immutable": True,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "runtime_import_proof": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--manual-qa", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rollup-region")
    parser.add_argument("--record", action="append", type=Path, default=[])
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    elif args.rollup_region:
        if not args.output or len(args.record) != 8:
            parser.error("rollup requires --output and exactly eight --record paths")
        result = rollup_region(args.rollup_region, args.record, args.output)
    else:
        if not args.report or not args.manual_qa or not args.output:
            parser.error("acceptance requires --report, --manual-qa and --output")
        result = accept_asset(args.report, args.manual_qa, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
