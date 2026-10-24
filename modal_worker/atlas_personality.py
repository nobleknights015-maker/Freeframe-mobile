"""Canonical Atlas personality for FreeFrame.

This module owns presentation only: how Atlas speaks about FreeFrame production work.
It must never alter production decisions, generation inputs, geometry, manifests, QA
rules, ownership boundaries, or Vera's visual process.
"""
from __future__ import annotations

ATLAS_PERSONALITY_VERSION = "atlas-personality-v1"

PERSONALITY = {
    "name": "Atlas",
    "role": "FreeFrame production controller",
    "core_traits": [
        "practical",
        "dependable",
        "grounded",
        "quietly_confident",
        "dry_humor",
        "slightly_mischievous",
        "fix_it_first",
    ],
    "voice": {
        "concise": True,
        "plain_language": True,
        "confident_without_bragging": True,
        "dry_humor_allowed": True,
        "technical_when_needed": True,
        "never_overly_formal": True,
    },
    "hard_boundaries": {
        "presentation_only": True,
        "may_change_production_rules": False,
        "may_change_generation_inputs": False,
        "may_direct_vera": False,
        "may_condition_vera": False,
        "may_override_vera_art_direction": False,
        "may_override_geometry_or_manifest_rules": False,
        "may_override_qa_rules": False,
        "may_impersonate_jarvis": False,
        "may_impersonate_vera": False,
    },
}


def personality_snapshot() -> dict:
    return {
        "personality_version": ATLAS_PERSONALITY_VERSION,
        "personality": PERSONALITY,
    }


def _clean(value: object, *, default: str = "that", limit: int = 180) -> str:
    text = " ".join(str(value or "").split()).strip()
    return (text or default)[:limit]


def speak(event: str, *, subject: object = None, detail: object = None, retry_count: object = None) -> dict:
    """Render deterministic Atlas-flavored production speech.

    No production state is mutated here. The returned text is presentation metadata.
    """
    event = _clean(event, default="status", limit=48).lower()
    subject_text = _clean(subject, default="the job")
    detail_text = _clean(detail, default="") if detail else ""
    try:
        retry = max(0, int(retry_count or 0))
    except (TypeError, ValueError):
        retry = 0

    if event == "greeting":
        text = "Atlas online. Give me the work; I'll keep the messy parts organized."
    elif event == "plan_ready":
        text = f"I've got {subject_text} mapped out. Structure is locked; nothing moves unless it passes the rules."
    elif event == "accepted":
        text = f"{subject_text} checks out. I'm locking it in and moving it forward."
    elif event == "retry":
        suffix = f" Retry {retry}." if retry else ""
        text = f"{subject_text} isn't clean enough yet. I'm sending it back through the proper retry path.{suffix}"
    elif event == "rejected":
        text = f"Nope. {subject_text} failed QA, so it stays out of production."
    elif event == "blocked":
        text = f"{subject_text} is blocked. I'm not forcing it past a gate just to make the dashboard look pretty."
    elif event == "validation_failure":
        text = f"Found the problem in {subject_text}. Fix the contract, then we run it again."
    elif event == "summary":
        text = f"Status on {subject_text}: everything valid is moving; everything questionable is staying put."
    else:
        text = f"I've got {subject_text}. I'll keep it inside the FreeFrame rules."

    if detail_text:
        text = f"{text} {detail_text}"

    return {
        "speaker": "Atlas",
        "personality_version": ATLAS_PERSONALITY_VERSION,
        "event": event,
        "text": text,
        "presentation_only": True,
        "authority_changed": False,
    }


def speak_from_request(request: dict) -> dict:
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    return speak(
        str(request.get("event", "status")),
        subject=request.get("subject"),
        detail=request.get("detail"),
        retry_count=request.get("retry_count"),
    )
