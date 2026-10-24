"""Project-owned style anchors for Plushbound production conditioning."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

STYLE_ANCHOR_LIBRARY_VERSION = "plushbound-style-anchor-v4-family-routed-normalized"
BASE_DIR = Path(__file__).with_name("project_references")
MIN_RENDER_REFERENCE_DIMENSION = 128


@dataclass(frozen=True)
class StyleAnchor:
    anchor_id: str
    path: str
    git_blob_sha1: str
    ownership: str
    role: str
    source_description: str

    def load_bytes(self) -> bytes:
        raw = (BASE_DIR / self.path).read_bytes()
        header = f"blob {len(raw)}\0".encode("utf-8")
        actual_blob = hashlib.sha1(header + raw).hexdigest()
        if actual_blob != self.git_blob_sha1:
            raise ValueError(f"style anchor Git blob hash mismatch for {self.anchor_id}")
        return raw

    def sha256(self) -> str:
        return hashlib.sha256(self.load_bytes()).hexdigest()

    def load_image(self):
        from PIL import Image
        import io
        raw = self.load_bytes()
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        width, height = image.size
        short_edge = min(width, height)
        if short_edge < MIN_RENDER_REFERENCE_DIMENSION:
            scale = MIN_RENDER_REFERENCE_DIMENSION / float(short_edge)
            target = (max(MIN_RENDER_REFERENCE_DIMENSION, round(width * scale)), max(MIN_RENDER_REFERENCE_DIMENSION, round(height * scale)))
            image = image.resize(target, Image.Resampling.LANCZOS)
        return image

    def metadata(self) -> dict:
        return {
            "library_version": STYLE_ANCHOR_LIBRARY_VERSION,
            "anchor_id": self.anchor_id,
            "path": self.path,
            "git_blob_sha1": self.git_blob_sha1,
            "sha256": self.sha256(),
            "ownership": self.ownership,
            "role": self.role,
            "source_description": self.source_description,
            "render_reference_min_dimension": MIN_RENDER_REFERENCE_DIMENSION,
        }


# Retained for provenance only. This legacy environment JPEG has valid JPEG markers
# but is structurally undecodable by Pillow and MUST NOT be selected for production.
ELYNDOR_NONCREATURE_LEGACY = StyleAnchor(
    anchor_id="elyndor_noncreature_style_v1_legacy_invalid",
    path="elyndor_noncreature_style_anchor.jpg",
    git_blob_sha1="cd5c514ba2a6bf59485143d94ebdd36ae9616f4a",
    ownership="project_owned",
    role="provenance_only_invalid_do_not_render",
    source_description="legacy project-owned Elyndor environment anchor retained only for provenance; failed Pillow verification on 2026-10-24",
)

FAMILY_STYLE_ANCHORS: dict[str, StyleAnchor] = {
    "guardian_friendly": StyleAnchor(
        anchor_id="guardian_friendly_bramblebuck_v1",
        path="guardian_friendly_bramblebuck.jpg",
        git_blob_sha1="1286660450bbefe6bf2473d3d4dd8b82263a39d1",
        ownership="project_owned",
        role="creature_family_render_material_style",
        source_description="project-owned friendly Guardian reference used for family-level rendering and living-textile material cues",
    ),
    "guardian_corrupt": StyleAnchor(
        anchor_id="guardian_corrupt_bramble_v1",
        path="guardian_corrupt_bramble.jpg",
        git_blob_sha1="6d848a78e27c9503379321c374905e9738b9b932",
        ownership="project_owned",
        role="creature_family_render_material_style",
        source_description="project-owned corrupt Guardian reference used for family-level rendering and living-textile material cues",
    ),
    "guardian_boss": StyleAnchor(
        anchor_id="guardian_boss_warden_v1",
        path="guardian_boss_warden.jpg",
        git_blob_sha1="5fc9faa41c0624dc741aeb1bd0776cc0be88b8f9",
        ownership="project_owned",
        role="creature_family_render_material_style",
        source_description="project-owned Guardian boss reference used for family-level rendering and living-textile material cues",
    ),
    "enemy_creature": StyleAnchor(
        anchor_id="enemy_creature_snag_v1",
        path="enemy_creature_snag.jpg",
        git_blob_sha1="275226ca2af8f95ba692cc080820cb09b126393e",
        ownership="project_owned",
        role="creature_family_render_material_style",
        source_description="project-owned enemy creature reference used for family-level rendering and living-textile material cues",
    ),
}


def get_style_anchor(family: str) -> StyleAnchor:
    family = str(family).strip()
    try:
        return FAMILY_STYLE_ANCHORS[family]
    except KeyError as exc:
        raise ValueError(f"unknown Plushbound creature style-anchor family: {family}") from exc
