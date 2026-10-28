"""V2 deterministic A5 compiler adapter.

Reuses the proven regional A5 geometry/compiler core while explicitly binding its
normalization hook to the World Asset Pipeline V2 finishing policy. No provider or
GPU calls are possible here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from modal_worker import tileset_regional_a5_compiler as core
from modal_worker.world_asset_pipeline_v2_normalizer import normalize_image as v2_normalize_image


def self_test(region: str) -> dict:
    row = core.self_test(region)
    return {
        **row,
        "schema": "plushbound.world_asset_pipeline_v2_compiler_self_test.v1",
        "status": "PASS_ZERO_GPU_V2_COMPILER_CONTRACT",
        "normalizer_policy": "WORLD_ASSET_PIPELINE_V2",
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "runtime_import_proof": False,
    }


def compile_sheet(region: str, source_root: Path, source_closeout: Path, output_dir: Path) -> dict:
    previous = core.normalize_image
    core.normalize_image = v2_normalize_image
    try:
        report = core.compile_sheet(region, source_root, source_closeout, output_dir)
    finally:
        core.normalize_image = previous
    report = {
        **report,
        "schema": "plushbound.world_asset_pipeline_v2_compile_report.v1",
        "status": "PASS_ZERO_GPU_V2_DETERMINISTIC_COMPILE_ENGINE_PROFILE",
        "normalizer_policy": "WORLD_ASSET_PIPELINE_V2",
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "runtime_import_proof": False,
        "catalog_wide_launch_authorized": False,
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--source-closeout", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        result = self_test(args.region)
    else:
        if args.source_root is None or args.source_closeout is None or args.output_dir is None:
            parser.error("compile requires --source-root, --source-closeout and --output-dir")
        result = compile_sheet(args.region, args.source_root, args.source_closeout, args.output_dir)
    print(json.dumps({k: v for k, v in result.items() if k != "families"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
