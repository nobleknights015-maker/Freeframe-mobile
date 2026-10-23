"""Pure-Python resumable batch orchestration for FreeFrame.

Generation and optional production inspection are injected so this module can
be stress-tested without a GPU. Retry variants are deterministic: a rejected
asset gets a stable alternate seed while preserving its asset identity and
checkpoint history.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Iterable

from batch_state import BatchState, load, save_atomic, stable_asset_id

GenerateFn = Callable[[dict[str, Any]], dict[str, Any]]
InspectFn = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
RetryTransformFn = Callable[[dict[str, Any], int], dict[str, Any]]


def deterministic_retry_variant(item: dict[str, Any], attempt: int) -> dict[str, Any]:
    """Return a retry-safe copy with a deterministic alternate seed.

    Attempt 1 preserves the original request. Later attempts advance the seed
    using a large odd stride, giving diffusion a new composition without
    changing the logical asset ID or mutating the caller's manifest item.
    """
    variant = dict(item)
    variant["retry_attempt"] = attempt
    if attempt > 1 and "seed" in variant:
        base = int(variant["seed"])
        variant["seed"] = (base + (attempt - 1) * 104729) % 2147483647
        if variant["seed"] == 0:
            variant["seed"] = 1
    return variant


def run_batch(
    items: Iterable[dict[str, Any]],
    state_path: str | Path,
    batch_id: str,
    generate: GenerateFn,
    *,
    inspect: InspectFn | None = None,
    max_attempts: int = 3,
    retry_delay_seconds: float = 0.0,
    retry_transform: RetryTransformFn = deterministic_retry_variant,
) -> BatchState:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
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
            variant = retry_transform(item, attempt)
            try:
                metadata = generate(variant)
                metadata = {
                    **metadata,
                    "retry_attempt": attempt,
                    "effective_seed": variant.get("seed"),
                }
                if inspect is not None:
                    inspection = inspect(variant, metadata)
                    metadata = {**metadata, "production_inspection": inspection}
                    if not inspection.get("accepted", False):
                        reasons = inspection.get("errors") or ["production inspection rejected asset"]
                        raise ValueError("; ".join(str(reason) for reason in reasons))
                state.mark_completed(asset_id, metadata)
                save_atomic(path, state)
                break
            except Exception as exc:
                state.mark_failed(asset_id, f"{type(exc).__name__}: {exc}", attempt)
                save_atomic(path, state)
                if attempt < max_attempts and retry_delay_seconds > 0:
                    time.sleep(retry_delay_seconds)

    return state
