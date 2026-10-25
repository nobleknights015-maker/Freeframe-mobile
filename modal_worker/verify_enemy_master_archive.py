from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LOCK = HERE / "enemy_master_archive_lock.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_ids(lock: dict) -> set[str]:
    ids: set[str] = set()
    for region in lock["regions"]:
        for local in range(1, lock["masters_per_region"] + 1):
            ids.add(f"reg/{region}/enemy-battle/{local:03d}")
    return ids


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def verify(lock_path: Path, manifest_path: Path, index_path: Path, parts: list[Path]) -> dict:
    errors: list[str] = []
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    if not lock.get("fail_closed"):
        fail(errors, "lock:not_fail_closed")

    expected_part_locks = lock.get("parts", [])
    if len(parts) != len(expected_part_locks):
        fail(errors, f"part_count:{len(parts)}!={len(expected_part_locks)}")
        return {"ok": False, "errors": errors}

    if sha256_file(manifest_path) != lock["archive_set_manifest"]["sha256"]:
        fail(errors, "archive_set_manifest:sha256")
    if sha256_file(index_path) != lock["recovery_index"]["sha256"]:
        fail(errors, "recovery_index:sha256")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))

    for key, expected in (
        ("expected_master_count", lock["expected_master_count"]),
        ("accepted_master_count", lock["expected_master_count"]),
        ("quarantined_master_count", 0),
        ("unique_asset_ids", lock["expected_unique_asset_ids"]),
        ("unique_png_sha256", lock["expected_unique_png_sha256"]),
    ):
        if manifest.get(key) != expected:
            fail(errors, f"manifest:{key}:{manifest.get(key)}!={expected}")

    assets = index.get("assets", [])
    if len(assets) != lock["expected_master_count"]:
        fail(errors, f"index:asset_count:{len(assets)}!={lock['expected_master_count']}")

    by_path: dict[str, dict] = {}
    asset_ids: set[str] = set()
    hashes: set[str] = set()
    for entry in assets:
        aid = entry.get("asset_id")
        path = entry.get("archive_path")
        digest = entry.get("sha256")
        if aid in asset_ids:
            fail(errors, f"index:duplicate_asset_id:{aid}")
        asset_ids.add(aid)
        if digest in hashes:
            fail(errors, f"index:duplicate_png_sha256:{digest}")
        hashes.add(digest)
        if path in by_path:
            fail(errors, f"index:duplicate_archive_path:{path}")
        by_path[path] = entry
        if entry.get("model") != lock["required_model"]:
            fail(errors, f"index:model:{aid}")
        if entry.get("preset") != lock["required_preset"]:
            fail(errors, f"index:preset:{aid}")
        if entry.get("renderer_route") != lock["required_renderer_route"]:
            fail(errors, f"index:renderer_route:{aid}")

    expected = expected_ids(lock)
    if asset_ids != expected:
        fail(errors, f"index:deterministic_id_set:missing={len(expected-asset_ids)}:extra={len(asset_ids-expected)}")

    archive_ids: set[str] = set()
    archive_hashes: set[str] = set()
    archive_paths: set[str] = set()
    manifest_parts = {p["filename"]: p for p in manifest.get("parts", [])}

    for path, part_lock in zip(parts, expected_part_locks):
        if path.name != part_lock["filename"]:
            fail(errors, f"part:filename:{path.name}!={part_lock['filename']}")
        actual_part_sha = sha256_file(path)
        if actual_part_sha != part_lock["sha256"]:
            fail(errors, f"part:sha256:{path.name}")
        mp = manifest_parts.get(part_lock["filename"])
        if not mp or mp.get("sha256") != part_lock["sha256"] or mp.get("master_count") != part_lock["master_count"]:
            fail(errors, f"manifest:part_binding:{part_lock['filename']}")

        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad:
                fail(errors, f"part:crc:{path.name}:{bad}")
            try:
                pm = json.loads(z.read("partition_manifest.json"))
            except Exception as exc:
                fail(errors, f"part:partition_manifest:{path.name}:{exc}")
                continue
            pngs = [n for n in z.namelist() if n.endswith(".png")]
            if len(pngs) != part_lock["master_count"]:
                fail(errors, f"part:png_count:{path.name}:{len(pngs)}")
            if pm.get("master_count") != part_lock["master_count"]:
                fail(errors, f"part:partition_count:{path.name}")
            pm_by_path = {e.get("archive_path"): e for e in pm.get("assets", [])}
            if set(pngs) != set(pm_by_path):
                fail(errors, f"part:partition_path_set:{path.name}")

            for rel in pngs:
                if rel not in by_path:
                    fail(errors, f"part:unindexed_path:{rel}")
                    continue
                data = z.read(rel)
                digest = hashlib.sha256(data).hexdigest()
                indexed = by_path[rel]
                partitioned = pm_by_path.get(rel, {})
                if digest != indexed.get("sha256"):
                    fail(errors, f"part:index_hash:{rel}")
                if digest != partitioned.get("sha256"):
                    fail(errors, f"part:partition_hash:{rel}")
                if len(data) != indexed.get("bytes"):
                    fail(errors, f"part:index_bytes:{rel}")
                aid = indexed.get("asset_id")
                if aid in archive_ids:
                    fail(errors, f"part:duplicate_asset_id:{aid}")
                archive_ids.add(aid)
                if digest in archive_hashes:
                    fail(errors, f"part:duplicate_png_sha256:{digest}")
                archive_hashes.add(digest)
                if rel in archive_paths:
                    fail(errors, f"part:duplicate_path:{rel}")
                archive_paths.add(rel)

    if archive_ids != expected:
        fail(errors, f"archive:deterministic_id_set:missing={len(expected-archive_ids)}:extra={len(archive_ids-expected)}")
    if len(archive_hashes) != lock["expected_unique_png_sha256"]:
        fail(errors, f"archive:unique_hashes:{len(archive_hashes)}")
    if archive_paths != set(by_path):
        fail(errors, f"archive:index_path_set:missing={len(set(by_path)-archive_paths)}:extra={len(archive_paths-set(by_path))}")

    return {
        "ok": not errors,
        "errors": errors,
        "master_count": len(archive_ids),
        "unique_asset_ids": len(archive_ids),
        "unique_png_sha256": len(archive_hashes),
        "quarantined_master_count": index.get("quarantined_master_count"),
        "archive_set": lock["canonical_archive_set"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Fail-closed verifier for the canonical Plushbound enemy master archive set.")
    ap.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--part", action="append", type=Path, required=True, help="Pass each archive part in lockfile order.")
    args = ap.parse_args()
    result = verify(args.lock, args.manifest, args.index, args.part)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
