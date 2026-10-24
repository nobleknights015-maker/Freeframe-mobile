"""CLI for producing tamper-evident Atlas master visual-review receipts.

This is intentionally human-driven. A green generation workflow proves rendering and
structural checks; a reviewer still decides whether each image actually matches the
Plushbound visual contract. The receipt binds those judgments to one exact workflow
run, commit and artifact digest.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from modal_worker.atlas_visual_gate import record_master_visual_review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--canary-version", required=True)
    parser.add_argument("--judgments-json", required=True)
    parser.add_argument("--output", default="atlas-master-visual-review.json")
    args = parser.parse_args()

    judgments_path = Path(args.judgments_json)
    judgments = json.loads(judgments_path.read_text(encoding="utf-8"))
    review = record_master_visual_review(
        workflow_run_id=args.workflow_run_id,
        head_sha=args.head_sha,
        artifact_digest=args.artifact_digest,
        canary_version=args.canary_version,
        judgments=judgments,
    )
    output = Path(args.output)
    output.write_text(json.dumps(review, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "bounded_gate_passed": review["bounded_gate_passed"],
        "failed_cases": review["failed_cases"],
        "review_digest": review["review_digest"],
        "output": str(output),
        "automatic_full_production_authorized": False,
        "catalog_wide_launch_authorized": False,
    }, indent=2))


if __name__ == "__main__":
    main()
