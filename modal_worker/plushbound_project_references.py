"""Approved project-owned visual references for Plushbound creature conditioning.

The committed images are small text-free crops derived from the user's own approved
Plushbound visual-bible sheets. They are intentionally reference-only inputs: they
must never be treated as output assets or as authorization for catalog production.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path

REFERENCE_LIBRARY_VERSION = "plushbound-project-reference-v1"
REFERENCE_ROOT = Path(__file__).with_name("project_references")


@dataclass(frozen=True)
class ProjectReference:
    reference_id: str
    family: str
    filename: str
    sha256: str
    source_sheet_sha256: str
    ownership: str = "project_owned"
    purpose: str = "visual_conditioning_only"

    @property
    def path(self) -> Path:
        return REFERENCE_ROOT / self.filename

    def verify(self) -> None:
        raw = self.path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != self.sha256:
            raise ValueError(
                f"reference hash mismatch for {self.reference_id}: {actual} != {self.sha256}"
            )

    def load_image(self):
        from PIL import Image
        self.verify()
        with Image.open(self.path) as image:
            image.load()
            return image.convert("RGB")

    def metadata(self) -> dict:
        data = asdict(self)
        data["library_version"] = REFERENCE_LIBRARY_VERSION
        return data


REFERENCES: dict[str, ProjectReference] = {
    "guardian_friendly": ProjectReference(
        reference_id="guardian_friendly",
        family="guardian_friendly",
        filename="guardian_friendly_bramblebuck.jpg",
        sha256="5170174b16576700f3d2c118a19b339fd85799262a1f7f4e85a5ae641fa6c756",
        source_sheet_sha256="b87fa178a00ef565ef07e677751d91ae973379f7980dea4966018655869d0490",
    ),
    "guardian_corrupt": ProjectReference(
        reference_id="guardian_corrupt",
        family="guardian_corrupt",
        filename="guardian_corrupt_bramble.jpg",
        sha256="110c9e25452d8e6445478a07e26d5b3f546411b4c0f5834de6a4cf90420d851c",
        source_sheet_sha256="80e1e645d4fe8116bdaf0e9af4ea255868b9a978a0efd5e5cc394ae0f39eea88",
    ),
    "guardian_boss": ProjectReference(
        reference_id="guardian_boss",
        family="guardian_boss",
        filename="guardian_boss_warden.jpg",
        sha256="dcf6abb21fe55f66f16e82c41b824cb30196c8221d8a23795a0260c4bc36cbf0",
        source_sheet_sha256="80e1e645d4fe8116bdaf0e9af4ea255868b9a978a0efd5e5cc394ae0f39eea88",
    ),
    "enemy_creature": ProjectReference(
        reference_id="enemy_creature",
        family="enemy_creature",
        filename="enemy_creature_snag.jpg",
        sha256="23136831e115f91cb988e9a17e33f583bff1b39b42824c52ee5596401dfef511",
        source_sheet_sha256="80e1e645d4fe8116bdaf0e9af4ea255868b9a978a0efd5e5cc394ae0f39eea88",
    ),
}


def get_project_reference(family: str) -> ProjectReference:
    try:
        reference = REFERENCES[family]
    except KeyError as exc:
        raise ValueError(f"no approved project reference for family: {family}") from exc
    if reference.ownership != "project_owned":
        raise ValueError(f"reference {family} is not project-owned")
    reference.verify()
    return reference


def reference_snapshot() -> dict:
    return {
        "library_version": REFERENCE_LIBRARY_VERSION,
        "references": {family: ref.metadata() for family, ref in REFERENCES.items()},
        "production_authorized": False,
    }
