"""Bank visually-approved canon portraits and deterministic face crops.

No generation occurs here. This module only validates exact reviewed workflow
artifacts, copies 288x384 RGBA portraits, derives 144x144 face assets
deterministically, and writes an auditable ledger alongside the banked sprite ledger.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

from PIL import Image
import numpy as np

INPUT_ROOT = Path("canon-bank-input")
BANK_ROOT = Path("modal_worker/canon_banked")
PORTRAIT_DIR = BANK_ROOT / "portraits"
FACE_DIR = BANK_ROOT / "faces"
LEDGER = BANK_ROOT / "canon_portrait_face_ledger_v1.json"
SPRITE_LEDGER = BANK_ROOT / "canon_sprite_ledger_v1.json"

SOURCES = {
    "chris_bourn": INPUT_ROOT / "chris" / "chris_bourn_portrait.png",
    "penney_nguyen": INPUT_ROOT / "batch" / "penney_nguyen_portrait.png",
    "lily": INPUT_ROOT / "batch" / "lily_portrait.png",
    "ethan": INPUT_ROOT / "batch" / "ethan_portrait.png",
}
DISPLAY_NAMES = {
    "chris_bourn": "Chris Bourn",
    "penney_nguyen": "Penney Nguyen",
    "lily": "Lily",
    "ethan": "Ethan",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required reviewed-evidence environment variable is missing: {name}")
    return value


def validate_portrait(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError(path)
    with Image.open(path) as image:
        image.load()
        rgba = image.convert("RGBA")
    if rgba.size != (288, 384):
        raise ValueError(f"portrait geometry mismatch for {path}: {rgba.size}")
    alpha = np.asarray(rgba.getchannel("A"))
    transparent_fraction = float((alpha < 16).mean())
    opaque_fraction = float((alpha > 127).mean())
    if not 0.05 <= transparent_fraction <= 0.85:
        raise ValueError(f"portrait alpha isolation suspicious for {path}: {transparent_fraction:.4f}")
    if opaque_fraction < 0.12:
        raise ValueError(f"portrait subject occupancy too small for {path}: {opaque_fraction:.4f}")
    return {
        "width": 288,
        "height": 384,
        "mode": "RGBA",
        "transparent_fraction": round(transparent_fraction, 6),
        "opaque_fraction": round(opaque_fraction, 6),
        "sha256": sha256(path),
    }


def derive_face(portrait: Path, destination: Path) -> dict:
    with Image.open(portrait) as image:
        rgba = image.convert("RGBA")
    arr = np.asarray(rgba)
    alpha = arr[..., 3]
    ys, xs = np.where(alpha > 127)
    if len(xs) == 0 or len(ys) == 0:
        raise ValueError(f"portrait has no opaque subject: {portrait}")
    left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)
    foreground_height = bottom - top

    # Locked deterministic v1 crop: upper subject, head-and-shoulders centered on
    # foreground alpha. Crop geometry comes from pixels, not generator guesses.
    side = int(round(max(150, min(220, foreground_height * 0.48))))
    center_x = (left + right) / 2.0
    center_y = top + foreground_height * 0.235
    x0 = int(round(center_x - side / 2.0))
    y0 = int(round(center_y - side / 2.0))
    x0 = max(0, min(rgba.width - side, x0))
    y0 = max(0, min(rgba.height - side, y0))

    crop = rgba.crop((x0, y0, x0 + side, y0 + side)).resize((144, 144), Image.Resampling.LANCZOS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    crop.save(destination, format="PNG", optimize=True)

    crop_alpha = np.asarray(crop.getchannel("A"))
    occupancy = float((crop_alpha > 127).mean())
    if not 0.28 <= occupancy <= 0.98:
        raise ValueError(f"derived face occupancy outside locked range for {portrait}: {occupancy:.4f}")
    return {
        "width": 144,
        "height": 144,
        "mode": "RGBA",
        "source_portrait": str(portrait),
        "source_foreground_bbox": [left, top, right, bottom],
        "crop_box": [x0, y0, x0 + side, y0 + side],
        "occupancy": round(occupancy, 6),
        "sha256": sha256(destination),
        "derivation": "alpha_bbox_head_shoulders_v1",
    }


def main() -> None:
    if not SPRITE_LEDGER.is_file():
        raise FileNotFoundError(f"existing banked sprite ledger is required: {SPRITE_LEDGER}")

    gate_path = Path(require_env("PORTRAIT_VISUAL_GATE_PATH"))
    gate_sha = require_env("PORTRAIT_VISUAL_GATE_SHA256")
    if not gate_path.is_file() or sha256(gate_path) != gate_sha:
        raise RuntimeError("visual gate file is missing or changed after workflow verification")
    visual_gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if visual_gate.get("status") != "PASS":
        raise RuntimeError("portrait visual gate is not PASS")

    source_artifacts = {
        "chris": {
            "run_id": int(require_env("CHRIS_RUN_ID")),
            "artifact_id": int(require_env("CHRIS_ARTIFACT_ID")),
            "artifact_name": require_env("CHRIS_ARTIFACT_NAME"),
            "artifact_digest": require_env("CHRIS_ARTIFACT_DIGEST"),
        },
        "batch": {
            "run_id": int(require_env("BATCH_RUN_ID")),
            "artifact_id": int(require_env("BATCH_ARTIFACT_ID")),
            "artifact_name": require_env("BATCH_ARTIFACT_NAME"),
            "artifact_digest": require_env("BATCH_ARTIFACT_DIGEST"),
        },
    }

    PORTRAIT_DIR.mkdir(parents=True, exist_ok=True)
    FACE_DIR.mkdir(parents=True, exist_ok=True)

    characters = {}
    for character_id, source in SOURCES.items():
        source_validation = validate_portrait(source)
        expected_hash = visual_gate["portrait_sha256"][character_id]
        if source_validation["sha256"] != expected_hash:
            raise ValueError(f"portrait differs from exact visually-reviewed hash: {character_id}")
        portrait_destination = PORTRAIT_DIR / f"{character_id}.png"
        shutil.copyfile(source, portrait_destination)
        copied_validation = validate_portrait(portrait_destination)
        if copied_validation["sha256"] != source_validation["sha256"]:
            raise ValueError(f"portrait copy hash mismatch: {character_id}")

        face_destination = FACE_DIR / f"{character_id}.png"
        face_validation = derive_face(portrait_destination, face_destination)
        characters[character_id] = {
            "display_name": DISPLAY_NAMES[character_id],
            "portrait": {
                "path": str(portrait_destination),
                "validation": copied_validation,
                "visual_review": "passed_exact_hash_gate_before_bank",
            },
            "face": {
                "path": str(face_destination),
                "validation": face_validation,
                "visual_review": "derived_from_visually_approved_portrait",
            },
        }

    ledger = {
        "version": "plushbound-canon-portrait-face-ledger-v1",
        "status": "banked",
        "sprite_ledger": str(SPRITE_LEDGER),
        "source_artifacts": source_artifacts,
        "visual_gate": {
            "path": str(gate_path),
            "sha256": gate_sha,
            "schema": visual_gate.get("schema"),
            "status": visual_gate.get("status"),
        },
        "character_count": len(characters),
        "portrait_count": len(characters),
        "face_count": len(characters),
        "new_runtime_assets_banked": len(characters) * 2,
        "proven_canon_runtime_assets_total": 12,
        "characters": characters,
        "generation": {
            "portraits": "reference_conditioned_flux2_klein_bounded",
            "faces": "deterministic_from_accepted_portraits_no_paid_generation",
        },
        "catalog_wide_launch_authorized": False,
    }
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(ledger, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
