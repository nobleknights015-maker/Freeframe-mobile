"""Compact health reporting for long-running FreeFrame production batches."""
from __future__ import annotations

from typing import Any


def build_run_report(state: Any) -> dict[str, Any]:
    completed = getattr(state, "completed", {})
    failed = getattr(state, "failed", {})
    total = int(getattr(state, "total", 0))
    attempts = [int(v.get("retry_attempt", 1)) for v in completed.values()]
    first_pass = sum(1 for n in attempts if n == 1)
    recovered = sum(1 for n in attempts if n > 1)
    failed_attempts = sum(int(v.get("attempts", 0)) for v in failed.values())
    done = len(completed)
    unresolved = len(failed)
    pending = max(total - done - unresolved, 0)
    return {
        "batch_id": str(getattr(state, "batch_id", "")),
        "total": total,
        "completed": done,
        "first_pass": first_pass,
        "recovered_by_retry": recovered,
        "unresolved": unresolved,
        "pending": pending,
        "failed_attempts": failed_attempts,
        "completion_rate": (done / total) if total else 1.0,
        "first_pass_rate": (first_pass / done) if done else 0.0,
        "retry_recovery_rate": (recovered / done) if done else 0.0,
        "healthy": unresolved == 0 and pending == 0,
    }


def should_pause_batch(report: dict[str, Any], *, max_unresolved_rate: float = 0.05) -> bool:
    """Circuit breaker for systemic failures, not isolated quarantined assets."""
    total = int(report.get("total", 0))
    unresolved = int(report.get("unresolved", 0))
    if total <= 0:
        return False
    return unresolved / total > max_unresolved_rate
