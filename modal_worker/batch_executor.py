"""Pure-Python resumable batch orchestration for FreeFrame.

Generation is injected so this module can be stress-tested without a GPU.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Iterable

from batch_state import BatchState, load, save_atomic, stable_asset_id

GenerateFn = Callable[[dict[str, Any]], dict[str, Any]]


def run_batch(
    items: Iterable[dict[str, Any]],
    state_path: str | Path,
    batch_id: str,
    generate: GenerateFn,
    *,
    max_attempts: int = 3,
    retry_delay_seconds: float = 0.0,
) -> BatchState:
    materialized = list(items)
    path = Path(state_path)
    if path.exists():
        state = load(path)
        if state.batch_id != batch_id:
            raise ValueError("checkpoint belongs to a different batch")
        if state.total != len(materialized):
            raise ValueError("checkpoint item count differs from requested batch")
    else:
        state = BatchState(batch_id=batch_id, total=len(materialized))
        save_atomic(path, state)

    for item in materialized:
        asset_id = stable_asset_id(
            str(item.get("path", "")),
            str(item.get("prompt", "")),
            str(item.get("profile", "")),
        )
        if asset_id in state.completed:
            continue

        previous_attempts = int(state.failed.get(asset_id, {}).get("attempts", 0))
        for attempt in range(previous_attempts + 1, max_attempts + 1):
            try:
                metadata = generate(item)
                state.mark_completed(asset_id, metadata)
                save_atomic(path, state)
                break
            except Exception as exc:  # executor records failures; caller decides exception types
                state.mark_failed(asset_id, f"{type(exc).__name__}: {exc}", attempt)
                save_atomic(path, state)
                if attempt < max_attempts and retry_delay_seconds > 0:
                    time.sleep(retry_delay_seconds)

    return state
