"""Deterministic sharding for safe large FreeFrame production runs."""
from __future__ import annotations

import hashlib
from typing import Any, Iterable


def shard_index(asset_id: str, shard_count: int) -> int:
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    digest = hashlib.sha256(asset_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def split_into_shards(items: Iterable[dict[str, Any]], shard_count: int) -> list[list[dict[str, Any]]]:
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    shards: list[list[dict[str, Any]]] = [[] for _ in range(shard_count)]
    for item in items:
        asset_id = str(item.get("asset_id") or "")
        if not asset_id:
            raise ValueError("every production item requires asset_id")
        shards[shard_index(asset_id, shard_count)].append(item)
    return shards


def shard_manifest(items: Iterable[dict[str, Any]], shard_count: int) -> dict[str, Any]:
    shards = split_into_shards(items, shard_count)
    return {
        "shard_count": shard_count,
        "total": sum(len(s) for s in shards),
        "shards": [
            {"index": i, "count": len(shard), "asset_ids": [str(x["asset_id"]) for x in shard]}
            for i, shard in enumerate(shards)
        ],
    }
