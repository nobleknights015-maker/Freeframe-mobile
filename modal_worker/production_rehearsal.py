"""Plan a small end-to-end rehearsal before any large Plushbound GPU batch."""
from __future__ import annotations

from typing import Any, Iterable

REHEARSAL_VERSION = "plushbound-production-rehearsal-v1"
DEFAULT_REHEARSAL_LIMIT = 32


def plan_rehearsal(items: Iterable[dict[str, Any]], *, limit: int = DEFAULT_REHEARSAL_LIMIT) -> dict[str, Any]:
    if not 1 <= limit <= 128:
        raise ValueError("rehearsal limit must be between 1 and 128")
    materialized = list(items)
    if not materialized:
        raise ValueError("rehearsal requires at least one asset")

    # Round-robin by profile so the rehearsal samples the factory instead of
    # accidentally taking only the first manifest category.
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in materialized:
        profile = str(item.get("profile") or "")
        asset_id = str(item.get("asset_id") or "")
        if not profile or not asset_id:
            raise ValueError("every rehearsal item requires profile and asset_id")
        groups.setdefault(profile, []).append(item)

    selected: list[dict[str, Any]] = []
    positions = {profile: 0 for profile in groups}
    profiles = sorted(groups)
    while len(selected) < min(limit, len(materialized)):
        progressed = False
        for profile in profiles:
            pos = positions[profile]
            if pos < len(groups[profile]) and len(selected) < limit:
                selected.append(groups[profile][pos]); positions[profile] += 1; progressed = True
        if not progressed:
            break

    return {
        "version": REHEARSAL_VERSION,
        "requested_limit": limit,
        "count": len(selected),
        "profiles": sorted({str(x["profile"]) for x in selected}),
        "asset_ids": [str(x["asset_id"]) for x in selected],
        "items": selected,
        "requires_explicit_full_batch_approval": True,
    }


def rehearsal_passes(report: dict[str, Any], *, min_completion_rate: float = 0.95, max_unresolved: int = 1) -> bool:
    """Conservative gate; passing rehearsal never authorizes the full batch."""
    return (
        int(report.get("total", 0)) > 0
        and float(report.get("completion_rate", 0.0)) >= min_completion_rate
        and int(report.get("unresolved", 0)) <= max_unresolved
    )
