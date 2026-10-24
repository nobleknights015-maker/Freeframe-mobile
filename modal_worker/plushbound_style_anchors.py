"""Project-owned non-creature style anchors for Plushbound conditioning."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

STYLE_ANCHOR_LIBRARY_VERSION = "plushbound-style-anchor-v2-git-pinned"
BASE_DIR = Path(__file__).with_name("project_references")


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
        image = Image.open(io.BytesIO(self.load_bytes()))
        image.verify()
        return Image.open(io.BytesIO(self.load_bytes())).convert("RGB")

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
        }


ELYNDOR_NONCREATURE = StyleAnchor(
    anchor_id="elyndor_noncreature_style_v1",
    path="elyndor_noncreature_style_anchor.jpg",
    git_blob_sha1="cd5c514ba2a6bf59485143d94ebdd36ae9616f4a",
    ownership="project_owned",
    role="render_palette_material_style_only",
    source_description="derived only from the user/project-owned Elyndor environment asset sheet; contains environment art and no creature anatomy",
)


def get_style_anchor(anchor_id: str = "elyndor_noncreature_style_v1") -> StyleAnchor:
    if anchor_id != ELYNDOR_NONCREATURE.anchor_id:
        raise ValueError(f"unknown Plushbound style anchor: {anchor_id}")
    return ELYNDOR_NONCREATURE
