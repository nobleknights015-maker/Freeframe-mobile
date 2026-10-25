from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "plushbound_enemy_runtime_spec.json"


def load_spec(path: Path = SPEC_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _source(enemy_id: int, frame_index: int, spec: dict) -> Image.Image:
    w, h = spec["canvas"]["width"], spec["canvas"]["height"]
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # Integer-only geometry: deterministic across CPU/PIL runs; transparent outside silhouette.
    cx = 48 + ((frame_index % 2) * 2 - 1)
    body = (cx - 15, 28, cx + 15, 70)
    seed = hashlib.sha256(f"enemy:{enemy_id}".encode()).digest()
    fill = (64 + seed[0] % 128, 64 + seed[1] % 128, 64 + seed[2] % 128, 255)
    d.ellipse((cx - 13, 12, cx + 13, 38), fill=fill)
    d.rounded_rectangle(body, radius=8, fill=fill)
    d.polygon([(cx - 14, 67), (cx - 24, 82), (cx - 6, 74)], fill=fill)
    d.polygon([(cx + 14, 67), (cx + 24, 82), (cx + 6, 74)], fill=fill)
    return im


def render(enemy_id: int, frame_index: int, spec: dict) -> Image.Image:
    im = _source(enemy_id, frame_index, spec)
    box = tuple(spec["crop"]["box"])
    out = im.crop(box)
    expected = tuple(spec["crop"]["output_size"])
    if out.size != expected:
        raise ValueError(f"crop geometry mismatch: {out.size} != {expected}")
    return out


def validate_image(im: Image.Image, spec: dict) -> list[str]:
    errors: list[str] = []
    if im.mode != spec["canvas"]["mode"]:
        errors.append(f"mode:{im.mode}")
    if im.size != tuple(spec["crop"]["output_size"]):
        errors.append(f"size:{im.size}")
    alpha = im.getchannel("A") if "A" in im.getbands() else None
    if alpha is None:
        errors.append("missing_alpha")
    elif alpha.getbbox() is None:
        errors.append("empty_alpha")
    return errors


def build(output_root: Path, enemy_ids: Iterable[int]) -> dict:
    spec = load_spec()
    runtime = output_root / "runtime"
    quarantine = output_root / "quarantine"
    runtime.mkdir(parents=True, exist_ok=True)
    quarantine.mkdir(parents=True, exist_ok=True)
    entries = []
    seen = set()
    for enemy_id in enemy_ids:
        for frame_index, frame in enumerate(spec["frames"]):
            name = spec["naming"]["pattern"].format(enemy_id=enemy_id, frame=frame_index)
            rel = f"runtime/{name}"
            im = render(enemy_id, frame_index, spec)
            errors = validate_image(im, spec)
            if rel in seen:
                errors.append("duplicate_path")
            seen.add(rel)
            target = (quarantine if errors else runtime) / name
            im.save(target, format="PNG", optimize=False)
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if errors:
                continue
            entries.append({
                "asset_id": f"enemy:{enemy_id:04d}:{frame}", "enemy_id": enemy_id,
                "frame": frame, "path": rel, "width": im.width, "height": im.height,
                "mode": im.mode, "sha256": digest,
            })
    manifest = {"schema_version": spec["manifest"]["schema_version"], "family": spec["family"], "assets": entries}
    (output_root / "enemy_runtime_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def build_canary(output_root: Path) -> dict:
    spec = load_spec()
    manifest = build(output_root, spec["canary"]["enemy_ids"])
    if len(manifest["assets"]) != spec["canary"]["expected_asset_count"]:
        raise RuntimeError("enemy canary did not produce the locked clean asset count")
    return manifest
