"""Atlas production-state ledger and tamper-evident QA receipts.

This module deliberately contains no model/GPU logic. It gives Atlas a deterministic
state machine that can sit on top of the existing crash-safe batch checkpoint layer.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

LEDGER_VERSION = "atlas-production-ledger-v2"
INITIAL_STATE = "planned"
FINAL_STATES = {"accepted", "quarantined"}
ATTEMPT_EVENTS = {"generation_succeeded", "generation_failed"}

ALLOWED_TRANSITIONS: dict[str, dict[str, str]] = {
    "planned": {"plan_validated": "ready"},
    "ready": {"generation_succeeded": "generated", "generation_failed": "generation_failed", "quarantine": "quarantined"},
    "generated": {"qa_passed": "accepted", "qa_failed": "qa_failed", "quarantine": "quarantined"},
    "generation_failed": {"queue_retry": "retry_queued", "quarantine": "quarantined"},
    "qa_failed": {"queue_retry": "retry_queued", "quarantine": "quarantined"},
    "retry_queued": {"generation_succeeded": "generated", "generation_failed": "generation_failed", "quarantine": "quarantined"},
    "accepted": {},
    "quarantined": {},
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _receipt_hash(previous_hash: str, event: str, state: str, metadata: dict[str, Any]) -> str:
    return hashlib.sha256(
        _canonical({"previous_hash": previous_hash, "event": event, "state": state, "metadata": metadata})
    ).hexdigest()


@dataclass
class AssetProductionRecord:
    atlas_job_id: str
    family: str
    plan_digest: str
    state: str = INITIAL_STATE
    attempts: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    version: str = LEDGER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "atlas_job_id": self.atlas_job_id,
            "family": self.family,
            "plan_digest": self.plan_digest,
            "state": self.state,
            "attempts": self.attempts,
            "history": list(self.history),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AssetProductionRecord":
        if value.get("version") != LEDGER_VERSION:
            raise ValueError("unsupported Atlas production ledger version")
        record = cls(
            atlas_job_id=str(value["atlas_job_id"]),
            family=str(value["family"]),
            plan_digest=str(value["plan_digest"]),
            state=str(value.get("state", INITIAL_STATE)),
            attempts=int(value.get("attempts", 0)),
            history=list(value.get("history", [])),
        )
        if record.state not in ALLOWED_TRANSITIONS:
            raise ValueError(f"unknown Atlas production state: {record.state}")
        if record.attempts < 0:
            raise ValueError("attempts cannot be negative")
        verify_history(record)
        return record


def new_record(atlas_job_id: str, family: str, plan_digest: str) -> AssetProductionRecord:
    if not atlas_job_id.strip() or not family.strip() or not plan_digest.strip():
        raise ValueError("atlas_job_id, family, and plan_digest are required")
    return AssetProductionRecord(atlas_job_id=atlas_job_id, family=family, plan_digest=plan_digest)


def transition(record: AssetProductionRecord, event: str, metadata: dict[str, Any] | None = None) -> AssetProductionRecord:
    if record.state in FINAL_STATES:
        raise ValueError(f"cannot transition final state {record.state}")
    event = str(event).strip()
    target = ALLOWED_TRANSITIONS.get(record.state, {}).get(event)
    if target is None:
        raise ValueError(f"event {event!r} is not valid from state {record.state!r}")
    metadata = dict(metadata or {})
    previous_hash = record.history[-1]["receipt_hash"] if record.history else "GENESIS"
    if event in ATTEMPT_EVENTS:
        record.attempts += 1
    receipt_hash = _receipt_hash(previous_hash, event, target, metadata)
    record.state = target
    record.history.append(
        {
            "sequence": len(record.history) + 1,
            "event": event,
            "state": target,
            "metadata": metadata,
            "previous_hash": previous_hash,
            "receipt_hash": receipt_hash,
        }
    )
    return record


def verify_history(record: AssetProductionRecord) -> None:
    previous_hash = "GENESIS"
    replay_state = INITIAL_STATE
    attempts = 0
    for expected_sequence, receipt in enumerate(record.history, start=1):
        if int(receipt.get("sequence", -1)) != expected_sequence:
            raise ValueError("Atlas receipt sequence is invalid")
        event = str(receipt.get("event", ""))
        target = ALLOWED_TRANSITIONS.get(replay_state, {}).get(event)
        if target is None or target != receipt.get("state"):
            raise ValueError("Atlas receipt contains an invalid state transition")
        metadata = dict(receipt.get("metadata", {}))
        if receipt.get("previous_hash") != previous_hash:
            raise ValueError("Atlas receipt chain is broken")
        calculated = _receipt_hash(previous_hash, event, target, metadata)
        if receipt.get("receipt_hash") != calculated:
            raise ValueError("Atlas receipt hash mismatch")
        if event in ATTEMPT_EVENTS:
            attempts += 1
        previous_hash = calculated
        replay_state = target
    if replay_state != record.state:
        raise ValueError("Atlas ledger state does not match receipt history")
    if attempts != record.attempts:
        raise ValueError("Atlas ledger attempt count does not match receipt history")


def summarize(records: list[AssetProductionRecord]) -> dict[str, Any]:
    counts = {state: 0 for state in ALLOWED_TRANSITIONS}
    attempts = 0
    for record in records:
        verify_history(record)
        counts[record.state] += 1
        attempts += record.attempts
    return {
        "ledger_version": LEDGER_VERSION,
        "total": len(records),
        "states": counts,
        "attempts": attempts,
        "complete": counts["accepted"],
        "needs_attention": counts["qa_failed"] + counts["generation_failed"] + counts["quarantined"],
        "automatic_full_production_authorized": False,
    }
