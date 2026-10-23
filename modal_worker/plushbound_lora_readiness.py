"""Fail-closed readiness checks for a future Plushbound FLUX.2 Klein 4B style LoRA.

This module never trains a model. It validates that a proposed training manifest is
large enough, diverse enough, high-resolution enough, content-captioned, and
explicitly user/project-owned before any paid training workflow may be enabled.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

TRAINING_TARGET = "black-forest-labs/FLUX.2-klein-base-4B"
INFERENCE_TARGET = "black-forest-labs/FLUX.2-klein-4B"
LORA_READINESS_VERSION = "plushbound-lora-readiness-v2"
MIN_IMAGES = 15
MAX_IMAGES = 40
MIN_CATEGORIES = 3
MIN_LONG_EDGE = 1024
ALLOWED_RIGHTS = {"user_owned", "project_owned"}
REQUIRED_TRIGGER = "PLUSHBOUNDMT"

# Style captions should describe content and let the shared visual treatment bake
# into the adapter. These phrases are common accidental style leakage for this project.
FORBIDDEN_STYLE_CAPTION_TERMS = (
    "anime style",
    "jrpg style",
    "rpg maker",
    "mv style",
    "trinity style",
    "painterly style",
    "rendering style",
    "plushbound style",
)


@dataclass(frozen=True)
class TrainingImage:
    asset_id: str
    category: str
    caption: str
    rights: str
    sha256: str
    width: int
    height: int


def _valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def evaluate_training_manifest(images: Iterable[TrainingImage]) -> dict:
    items = list(images)
    reasons: list[str] = []

    if not MIN_IMAGES <= len(items) <= MAX_IMAGES:
        reasons.append(f"dataset must contain {MIN_IMAGES}-{MAX_IMAGES} images")

    ids = [item.asset_id for item in items]
    if len(ids) != len(set(ids)):
        reasons.append("asset ids must be unique")

    hashes = [item.sha256.lower() for item in items]
    if any(not _valid_sha256(value) for value in hashes):
        reasons.append("every image requires a valid sha256")
    if len(hashes) != len(set(hashes)):
        reasons.append("duplicate image hashes are not allowed")

    if any(item.rights not in ALLOWED_RIGHTS for item in items):
        reasons.append("all images must be explicitly user-owned or project-owned")

    if any(item.width <= 0 or item.height <= 0 for item in items):
        reasons.append("every image requires positive pixel dimensions")
    if any(max(item.width, item.height) < MIN_LONG_EDGE for item in items):
        reasons.append(f"every image must be at least {MIN_LONG_EDGE}px on its long edge")

    captions = [item.caption.strip() for item in items]
    if any(not caption for caption in captions):
        reasons.append("every image requires a non-empty content caption")
    if any(REQUIRED_TRIGGER.lower() not in caption.lower() for caption in captions if caption):
        reasons.append(f"every caption must include the trigger {REQUIRED_TRIGGER}")
    if any(
        term in caption.lower()
        for caption in captions
        for term in FORBIDDEN_STYLE_CAPTION_TERMS
    ):
        reasons.append("style captions must describe content rather than naming the visual style")

    categories = Counter(item.category.strip() for item in items if item.category.strip())
    if len(categories) < MIN_CATEGORIES:
        reasons.append(f"dataset must span at least {MIN_CATEGORIES} visual categories")

    # A style dataset should not collapse into one subject type. No single category
    # may dominate more than 70% of an otherwise-valid dataset.
    if items and categories and max(categories.values()) / len(items) > 0.70:
        reasons.append("no single visual category may exceed 70% of the dataset")

    return {
        "version": LORA_READINESS_VERSION,
        "training_target": TRAINING_TARGET,
        "inference_target": INFERENCE_TARGET,
        "trigger": REQUIRED_TRIGGER,
        "image_count": len(items),
        "categories": dict(sorted(categories.items())),
        "minimum_long_edge": MIN_LONG_EDGE,
        "rights_allowed": sorted(ALLOWED_RIGHTS),
        "ready": not reasons,
        "reasons": reasons,
        "training_authorized": False,
    }
