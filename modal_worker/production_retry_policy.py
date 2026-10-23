"""Production retry policy for large FreeFrame batches.

Keeps retry behavior explicit and bounded so a 22k-asset run cannot silently
turn a handful of difficult assets into runaway GPU spend.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    seed_stride: int = 104729
    quarantine_after_exhaustion: bool = True

    def validate(self) -> None:
        if not 1 <= self.max_attempts <= 8:
            raise ValueError("max_attempts must be between 1 and 8")
        if self.seed_stride <= 0:
            raise ValueError("seed_stride must be positive")

    def variant(self, item: dict[str, Any], attempt: int) -> dict[str, Any]:
        self.validate()
        if not 1 <= attempt <= self.max_attempts:
            raise ValueError("attempt outside retry policy")
        out = dict(item)
        out["retry_attempt"] = attempt
        if attempt > 1 and "seed" in out:
            seed = (int(out["seed"]) + (attempt - 1) * self.seed_stride) % 2147483647
            out["seed"] = seed or 1
        return out

    def exhausted_record(self, item: dict[str, Any], error: str) -> dict[str, Any]:
        return {
            "path": str(item.get("path", "")),
            "profile": str(item.get("profile", "")),
            "seed": item.get("seed"),
            "attempts": self.max_attempts,
            "error": error,
            "quarantined": self.quarantine_after_exhaustion,
        }


DEFAULT_PRODUCTION_RETRY_POLICY = RetryPolicy()
