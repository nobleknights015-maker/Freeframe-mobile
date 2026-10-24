"""4x turbo wrapper for Plushbound MAX MODE production.

The validated production runner historically maps one logical round to one 32-item
block per family shard. Turbo mode keeps that proven runner unchanged and maps each
new turbo round to four non-overlapping legacy 32-item blocks. This preserves stable
asset IDs, seeds, retry/inspection behavior, and the clean cutover after round 10.
"""
from __future__ import annotations

import argparse
import json
import pathlib

from modal_worker.max_production_round import ITEMS_PER_SHARD, OUT_ROOT, _run

TURBO_START_ROUND = 11
SUBLANES_PER_SHARD = 4
MODE = "MAX_MODE_12_STREAM_4X"


def effective_round(turbo_round: int, sublane: int) -> int:
    if turbo_round < TURBO_START_ROUND:
        raise ValueError(f"turbo round must be >= {TURBO_START_ROUND}")
    if sublane < 0 or sublane >= SUBLANES_PER_SHARD:
        raise ValueError(f"sublane must be 0..{SUBLANES_PER_SHARD - 1}")
    return TURBO_START_ROUND + (turbo_round - TURBO_START_ROUND) * SUBLANES_PER_SHARD + sublane


def run_turbo(shard: int, turbo_round: int, sublane: int) -> dict:
    mapped_round = effective_round(turbo_round, sublane)
    report = _run(int(shard), mapped_round)
    report["mode"] = MODE
    report["turbo_round"] = int(turbo_round)
    report["sublane"] = int(sublane)
    report["effective_legacy_round"] = mapped_round
    report["items_per_sublane"] = ITEMS_PER_SHARD
    report["sublanes_per_shard"] = SUBLANES_PER_SHARD

    report_path = pathlib.Path(OUT_ROOT) / f"round-{mapped_round:04d}" / f"shard-{int(shard)}" / "report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int, required=True, choices=(0, 1, 2, 3))
    parser.add_argument("--round-number", type=int, required=True)
    parser.add_argument("--sublane", type=int, required=True, choices=tuple(range(SUBLANES_PER_SHARD)))
    args = parser.parse_args()
    report = run_turbo(args.shard, args.round_number, args.sublane)
    print(json.dumps({k: v for k, v in report.items() if k != "assets"}, sort_keys=True))


if __name__ == "__main__":
    main()
