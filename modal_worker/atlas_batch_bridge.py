"""Bridge Atlas plans to the existing resumable FreeFrame batch engine."""
from __future__ import annotations

from typing import Any

try:
    from .atlas_production_ledger import AssetProductionRecord, transition
    from .batch_state import BatchState, stable_asset_id
except ImportError:
    from atlas_production_ledger import AssetProductionRecord, transition
    from batch_state import BatchState, stable_asset_id

BRIDGE_VERSION = "atlas-batch-bridge-v1"


def build_batch_item(plan: dict[str, Any], *, path: str, profile: str) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")
    if not plan.get("generation_supported"):
        raise ValueError("Atlas plan does not support direct image generation")
    request = plan.get("generation_request")
    if not isinstance(request, dict):
        raise ValueError("Atlas plan is missing generation_request")
    atlas_job_id = str(plan.get("atlas_job_id", "")).strip()
    plan_digest = str(plan.get("plan_digest", "")).strip()
    if not atlas_job_id or not plan_digest:
        raise ValueError("Atlas plan is missing production identity")
    if not str(path).strip() or not str(profile).strip():
        raise ValueError("path and profile are required")
    return {
        **request,
        "path": str(path),
        "profile": str(profile),
        "atlas_job_id": atlas_job_id,
        "plan_digest": plan_digest,
        "atlas_ledger_record": dict(plan["ledger_record"]),
        "atlas_bridge_version": BRIDGE_VERSION,
    }


def reconcile_batch_item(item: dict[str, Any], state: BatchState) -> AssetProductionRecord:
    if not isinstance(item, dict):
        raise ValueError("item must be an object")
    raw_record = item.get("atlas_ledger_record")
    if not isinstance(raw_record, dict):
        raise ValueError("batch item is missing atlas_ledger_record")
    record = AssetProductionRecord.from_dict(raw_record)
    if record.state == "planned":
        transition(record, "plan_validated", {"source": BRIDGE_VERSION})

    asset_id = stable_asset_id(str(item.get("path", "")), str(item.get("prompt", "")), str(item.get("profile", "")))
    if asset_id in state.completed:
        metadata = dict(state.completed[asset_id])
        transition(record, "generation_succeeded", {
            "asset_id": asset_id,
            "sha256": metadata.get("sha256"),
            "retry_attempt": metadata.get("retry_attempt"),
        })
        inspection = metadata.get("production_inspection")
        if isinstance(inspection, dict) and inspection.get("accepted") is False:
            transition(record, "qa_failed", {"errors": list(inspection.get("errors") or [])})
        else:
            transition(record, "qa_passed", {"source": "batch_checkpoint"})
        return record

    failure = state.failed.get(asset_id)
    if failure:
        attempts = max(1, int(failure.get("attempts", 1)))
        for attempt in range(attempts):
            if record.state == "ready" or record.state == "retry_queued":
                transition(record, "generation_succeeded", {"asset_id": asset_id, "attempt": attempt + 1, "result": "failed_or_rejected"})
            if record.state == "generated":
                transition(record, "qa_failed", {"error": str(failure.get("error", "batch failure"))})
            if attempt < attempts - 1:
                transition(record, "queue_retry", {"source": "batch_checkpoint"})
        return record

    return record


def batch_progress(items: list[dict[str, Any]], state: BatchState) -> dict[str, Any]:
    records = [reconcile_batch_item(item, state) for item in items]
    counts: dict[str, int] = {}
    for record in records:
        counts[record.state] = counts.get(record.state, 0) + 1
    return {
        "bridge_version": BRIDGE_VERSION,
        "batch_id": state.batch_id,
        "total": len(items),
        "states": counts,
        "accepted": counts.get("accepted", 0),
        "qa_failed": counts.get("qa_failed", 0),
        "ready_or_pending": counts.get("ready", 0) + counts.get("planned", 0) + counts.get("retry_queued", 0),
        "automatic_full_production_authorized": False,
    }
