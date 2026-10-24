"""Fail-closed Atlas visual-review receipts for bounded production evidence.

A workflow succeeding only proves that images were generated. This module records an
explicit visual review against named cases and keeps that review tied to one exact
workflow head and artifact digest. It never authorizes catalog-wide production.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

VISUAL_GATE_VERSION = "atlas-visual-gate-v1"
CREATURE_CANARY_CASES = (
    "guardian_friendly_quadruped",
    "guardian_friendly_winged",
    "guardian_friendly_biped",
    "guardian_friendly_long_low",
    "guardian_corrupt_low",
    "guardian_boss_hexapod",
    "enemy_creature_hexapod",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def record_creature_visual_review(
    *,
    workflow_run_id: int,
    head_sha: str,
    artifact_digest: str,
    canary_version: str,
    judgments: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if workflow_run_id <= 0:
        raise ValueError("workflow_run_id must be positive")
    if len(str(head_sha).strip()) != 40:
        raise ValueError("head_sha must be a full 40-character commit SHA")
    if not str(artifact_digest).startswith("sha256:") or len(str(artifact_digest)) != 71:
        raise ValueError("artifact_digest must be a sha256: digest")
    if not str(canary_version).strip():
        raise ValueError("canary_version is required")
    if not isinstance(judgments, dict):
        raise ValueError("judgments must be an object")

    expected = set(CREATURE_CANARY_CASES)
    supplied = set(judgments)
    missing = sorted(expected - supplied)
    extra = sorted(supplied - expected)
    if missing or extra:
        raise ValueError(f"visual review case mismatch; missing={missing}, extra={extra}")

    normalized: dict[str, dict[str, Any]] = {}
    for case_id in CREATURE_CANARY_CASES:
        item = judgments[case_id]
        if not isinstance(item, dict) or not isinstance(item.get("passed"), bool):
            raise ValueError(f"{case_id} must include boolean passed")
        reasons = item.get("reasons", [])
        if not isinstance(reasons, list) or any(not str(reason).strip() for reason in reasons):
            raise ValueError(f"{case_id} reasons must be a list of non-empty strings")
        if not item["passed"] and not reasons:
            raise ValueError(f"failed case {case_id} requires at least one reason")
        normalized[case_id] = {
            "passed": item["passed"],
            "reasons": [str(reason).strip() for reason in reasons],
        }

    passed_cases = [case_id for case_id, value in normalized.items() if value["passed"]]
    failed_cases = [case_id for case_id, value in normalized.items() if not value["passed"]]
    bounded_gate_passed = not failed_cases
    body = {
        "visual_gate_version": VISUAL_GATE_VERSION,
        "workflow_run_id": workflow_run_id,
        "head_sha": head_sha,
        "artifact_digest": artifact_digest,
        "canary_version": canary_version,
        "required_cases": list(CREATURE_CANARY_CASES),
        "judgments": normalized,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "bounded_gate_passed": bounded_gate_passed,
        "scope": "creature-master visual canary only",
        "automatic_full_production_authorized": False,
    }
    body["review_digest"] = hashlib.sha256(_canonical(body)).hexdigest()
    return body
