"""Direct CLI for Plushbound max-mode shards.

Unlike `modal run`, this process does not create a new ephemeral Modal app. It calls
only the already-deployed freeframe-worker/FreeFrameProductionGenerator, avoiding
Modal AppCreate rate limits during parallel production.
"""
from __future__ import annotations

import argparse
import json

from modal_worker.max_production_round import _run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=int, required=True, choices=(0, 1, 2, 3))
    parser.add_argument("--round-number", type=int, required=True)
    args = parser.parse_args()
    report = _run(args.shard, args.round_number)
    print(json.dumps({k: v for k, v in report.items() if k != "assets"}, sort_keys=True))


if __name__ == "__main__":
    main()
