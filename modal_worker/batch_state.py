"""Crash-safe batch manifest state for FreeFrame cloud jobs."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BatchState:
    batch_id: str
    total: int
    completed: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed: dict[str, dict[str, Any]] = field(default_factory=dict)
    version: int = 1

    @property
    def done(self) -> int:
        return len(self.completed)

    @property
    def pending(self) -> int:
        return max(0, self.total - self.done)

    def mark_completed(self, asset_id: str, metadata: dict[str, Any]) -> None:
        self.completed[asset_id] = metadata
        self.failed.pop(asset_id, None)

    def mark_failed(self, asset_id: str, error: str, attempts: int) -> None:
        if asset_id in self.completed:
            return
        self.failed[asset_id] = {"error": error, "attempts": attempts}

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "batch_id": self.batch_id, "total": self.total, "completed": self.completed, "failed": self.failed}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BatchState":
        if value.get("version") != 1:
            raise ValueError("unsupported batch manifest version")
        total = int(value["total"])
        if total < 0:
            raise ValueError("batch total cannot be negative")
        completed = dict(value.get("completed", {})); failed = dict(value.get("failed", {}))
        if set(completed) & set(failed):
            raise ValueError("asset cannot be both completed and failed")
        if len(completed) > total:
            raise ValueError("completed asset count exceeds batch total")
        return cls(batch_id=str(value["batch_id"]), total=total, completed=completed, failed=failed)


def stable_asset_id(path: str, prompt: str, profile: str) -> str:
    return hashlib.sha256(f"{path}\0{prompt}\0{profile}".encode("utf-8")).hexdigest()[:24]


def _encode(state: BatchState) -> bytes:
    return json.dumps(state.to_dict(), sort_keys=True, indent=2).encode("utf-8")


def save_atomic(path: str | Path, state: BatchState) -> None:
    destination = Path(path); destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.with_suffix(destination.suffix + ".bak")
    encoded = _encode(state)
    fd, tmp_name = tempfile.mkstemp(prefix=destination.name + ".", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
        if destination.exists():
            shutil.copyfile(destination, backup)
        os.replace(tmp_name, destination)
    finally:
        if os.path.exists(tmp_name): os.unlink(tmp_name)


def _load_one(path: Path) -> BatchState:
    with path.open("r", encoding="utf-8") as handle:
        return BatchState.from_dict(json.load(handle))


def load(path: str | Path) -> BatchState:
    source = Path(path)
    try:
        return _load_one(source)
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as primary:
        backup = source.with_suffix(source.suffix + ".bak")
        if not backup.exists():
            raise
        try:
            return _load_one(backup)
        except Exception as backup_error:
            raise ValueError(f"primary and backup batch checkpoints are unreadable: {primary}; {backup_error}") from backup_error
