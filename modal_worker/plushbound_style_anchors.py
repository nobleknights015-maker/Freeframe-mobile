"""Project-owned non-creature style anchors for Plushbound conditioning."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path

STYLE_ANCHOR_LIBRARY_VERSION = "plushbound-style-anchor-v1"
BASE_DIR = Path(__file__).with_name("project_references")


@dataclass(frozen=True)
class StyleAnchor:
    anchor_id: str
    path: str
    sha256: str
    ownership: str
    role: str
    source_description: str

    def load_bytes(self) -> bytes:
        raw = (BASE_DIR / self.path).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != self.sha256:
            raise ValueError(f"style anchor hash mismatch for {self.anchor_id}")
        return raw

    def load_image(self):
        from PIL import Image
        import io
        return Image.open(io.BytesIO(self.load_bytes())).convert("RGB")

    def metadata(self) -> dict:
        return {**asdict(self), "library_version": STYLE_ANCHOR_LIBRARY_VERSION}


ELYNDOR_NONCREATURE = StyleAnchor(
    anchor_id="elyndor_noncreature_style_v1",
    path="elyndor_noncreature_style_anchor.jpg",
    sha256="91544df958737c23040eac4bb46296355176f62c88a8bb1cec7d4917f55ec340",
    ownership="project_owned",
    role="render_palette_material_style_only",
    source_description="derived only from the user/project-owned Elyndor environment asset sheet; contains environment art and no creature anatomy",
)


def get_style_anchor(anchor_id: str = "elyndor_noncreature_style_v1") -> StyleAnchor:
    if anchor_id != ELYNDOR_NONCREATURE.anchor_id:
        raise ValueError(f"unknown Plushbound style anchor: {anchor_id}")
    return ELYNDOR_NONCREATURE
