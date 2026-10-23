"""Fail-closed receipt for promoting the Plushbound character render style.

A character style lock is visual-QA evidence, not a boolean feature flag.  The
receipt binds an explicit approval to the exact production profile/version and
benchmark image hash that was reviewed.  This module never authorizes full batch
production; it only allows the bounded four-image canary gate to proceed.
"""
from __future__ import annotations

from dataclasses import dataclass

from modal_worker.production_style_policy import (
    PRODUCTION_STYLE_POLICY_VERSION,
    style_for_preset,
)
from modal_worker.style_profiles import STYLE_PROFILE_VERSION

STYLE_LOCK_VERSION = "plushbound-character-style-lock-v1"
CHARACTER_PRESET = "plushbound_character"


@dataclass(frozen=True)
class CharacterStyleLockReceipt:
    approved: bool
    reviewer: str
    benchmark_sha256: str
    profile: str
    profile_version: str
    policy_version: str
    note: str = ""


def _valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def evaluate_character_style_lock(receipt: CharacterStyleLockReceipt | None) -> dict:
    reasons: list[str] = []
    expected_profile = style_for_preset(CHARACTER_PRESET)

    if receipt is None:
        reasons.append("explicit character visual-QA receipt is required")
    else:
        if receipt.approved is not True:
            reasons.append("character visual QA must be explicitly approved")
        if not receipt.reviewer.strip():
            reasons.append("character visual QA requires a reviewer label")
        if not _valid_sha256(receipt.benchmark_sha256.lower()):
            reasons.append("character visual QA requires a valid benchmark sha256")
        if receipt.profile != expected_profile:
            reasons.append("character style receipt does not match the production profile")
        if receipt.profile_version != STYLE_PROFILE_VERSION:
            reasons.append("character style receipt does not match the current profile version")
        if receipt.policy_version != PRODUCTION_STYLE_POLICY_VERSION:
            reasons.append("character style receipt does not match the current style policy version")

    return {
        "version": STYLE_LOCK_VERSION,
        "preset": CHARACTER_PRESET,
        "expected_profile": expected_profile,
        "expected_profile_version": STYLE_PROFILE_VERSION,
        "expected_policy_version": PRODUCTION_STYLE_POLICY_VERSION,
        "ready": not reasons,
        "reasons": reasons,
        "full_production_authorized": False,
    }
