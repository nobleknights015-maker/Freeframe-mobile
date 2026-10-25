"""Modal production runner for canonical enemy masters -> static 288x288 battlers.

Run only after ``verify_enemy_master_archive.py`` succeeds on the exact canonical
archive set. This runner consumes restored master PNGs and calls the already frozen
FreeFrame BiRefNet extractor; it performs no diffusion generation.
"""
from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import modal

from enemy_master_runtime_production import (
    EXPECTED_TOTAL,
    REQUIRED_EXTRACTOR_MODEL,
    REQUIRED_EXTRACTOR_PROVIDER,
    derive_one,
    expected_asset_ids,
    load_recovery_index,
)

APP_NAME = "freeframe-enemy-master-runtime-production"
EXTRACTOR_APP = "freeframe-worker"
EXTRACTOR_CLASS = "FreeFrameExtractor"
OUT_ROOT = Path("enemy-master-runtime-production")
app = modal.App(APP_NAME)


def _source_path(master_root: Path, archive_path: str) -> Path:
    path = master_root / archive_path
    if not path.is_file():
        raise RuntimeError(f"missing canonical master: {archive_path}")
    return path


def _extract(raw: bytes) -> tuple[bytes, str, str]:
    extractor = modal.Cls.from_name(EXTRACTOR_APP, EXTRACTOR_CLASS)()
    response = extractor.extract.remote({
        "image_base64": base64.b64encode(raw).decode("ascii")
    })
    try:
        png = base64.b64decode(response["image_base64"], validate=True)
    except Exception as exc:
        raise RuntimeError(f"extractor returned invalid image_base64: {exc}") from exc
    return png, str(response.get("provider")), str(response.get("model"))


def _process(master_root: Path, record) -> dict:
    source = _source_path(master_root, record.archive_path)
    raw = source.read_bytes()
    out_png, manifest = derive_one(record, raw, _extract)
    output = OUT_ROOT / (record.asset_id + ".png")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(out_png)
    manifest["path"] = str(output.relative_to(OUT_ROOT))
    return manifest


def _parse_canary(raw: str) -> list[str]:
    if not raw.strip():
        return []
    ids = [part.strip() for part in raw.split(",") if part.strip()]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate canary asset IDs")
    return ids


@app.local_entrypoint()
def main(
    master_root: str,
    recovery_index: str,
    max_parallel: int = 6,
    canary_assets: str = "",
):
    if not 1 <= max_parallel <= 10:
        raise ValueError("max_parallel must be 1..10")
    root = Path(master_root)
    records = load_recovery_index(Path(recovery_index))
    canary = _parse_canary(canary_assets)
    selected = canary if canary else list(expected_asset_ids())
    unknown = [aid for aid in selected if aid not in records]
    if unknown:
        raise RuntimeError(f"unknown canary/production asset IDs: {unknown}")

    results: list[dict] = []
    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {
            pool.submit(_process, root, records[aid]): aid
            for aid in selected
        }
        for future in as_completed(futures):
            aid = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"asset_id": aid, "error": str(exc)})

    results.sort(key=lambda row: row["asset_id"])
    failures.sort(key=lambda row: row["asset_id"])
    mode = "canary" if canary else "full"
    report = {
        "schema": "plushbound.enemy_master_runtime_production.v1",
        "mode": mode,
        "source_archive_set": "plushbound_enemy_masters_v1_640",
        "expected_source_masters": EXPECTED_TOTAL,
        "requested_assets": len(selected),
        "completed_assets": len(results),
        "failed_assets": len(failures),
        "derived_per_master": 1,
        "diffusion_generation_count": 0,
        "extractor_provider": REQUIRED_EXTRACTOR_PROVIDER,
        "extractor_model": REQUIRED_EXTRACTOR_MODEL,
        "output_geometry": [288, 288],
        "output_layout": "single",
        "assets": results,
        "failures": failures,
    }
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "batch-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k not in {"assets", "failures"}}, sort_keys=True))
    if failures or len(results) != len(selected):
        raise RuntimeError(
            f"enemy master runtime production incomplete: completed={len(results)} failures={len(failures)}"
        )
