"""Reviewed evidence for the current Plushbound character style lock.

The hash below is the exact PNG from the successful serialized four-lane Klein L4
canary (GitHub Actions run 39974097252). Updating the character profile or style
policy invalidates this receipt automatically through character_style_lock checks.
"""
from character_style_lock import CharacterStyleLockReceipt
from production_style_policy import PRODUCTION_STYLE_POLICY_VERSION, style_for_preset
from style_profiles import STYLE_PROFILE_VERSION

CHARACTER_CANARY_RUN_ID = 39974097252
CHARACTER_CANARY_SHA256 = "090ca99d917894ec59373907a8255b927029ebca6f1356706fab48798a9d4ccf"

APPROVED_CHARACTER_STYLE_LOCK = CharacterStyleLockReceipt(
    approved=True,
    reviewer="bounded-visual-qa-2026-10-23",
    benchmark_sha256=CHARACTER_CANARY_SHA256,
    profile=style_for_preset("plushbound_character"),
    profile_version=STYLE_PROFILE_VERSION,
    policy_version=PRODUCTION_STYLE_POLICY_VERSION,
    note=(
        "Serialized Klein L4 canary reviewed: single full-body adult adventurer, "
        "one continuous scene, normal anatomy, no turnaround/grid duplication."
    ),
)
