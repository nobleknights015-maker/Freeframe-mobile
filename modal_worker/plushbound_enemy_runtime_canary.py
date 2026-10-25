from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from PIL import Image

try:
    from .plushbound_enemy_runtime_production import build_canary, load_spec
except ImportError:
    from plushbound_enemy_runtime_production import build_canary, load_spec


def validate_canary(root: Path) -> dict:
    spec = load_spec()
    manifest = build_canary(root)
    errors: list[str] = []
    assets = manifest.get("assets", [])
    required = set(spec["manifest"]["required_fields"])
    expected_count = spec["canary"]["expected_asset_count"]
    if len(assets) != expected_count:
        errors.append(f"asset_count:{len(assets)}!={expected_count}")

    paths: set[str] = set()
    expected_size = tuple(spec["crop"]["output_size"])
    expected_mode = spec["canvas"]["mode"]
    for entry in assets:
        missing = required - set(entry)
        if missing:
            errors.append(f"missing_fields:{entry.get('asset_id','?')}:{sorted(missing)}")
            continue
        rel = entry["path"]
        if rel in paths:
            errors.append(f"duplicate_path:{rel}")
        paths.add(rel)
        path = root / rel
        if not path.is_file():
            errors.append(f"missing_file:{rel}")
            continue
        with Image.open(path) as im:
            im.load()
            if im.size != expected_size:
                errors.append(f"dimensions:{rel}:{im.size}")
            if im.mode != expected_mode:
                errors.append(f"mode:{rel}:{im.mode}")
            if "A" not in im.getbands() or im.getchannel("A").getbbox() is None:
                errors.append(f"alpha:{rel}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            errors.append(f"sha256:{rel}")

    quarantine = root / "quarantine"
    quarantined = sorted(p.name for p in quarantine.glob("*.png")) if quarantine.exists() else []
    if quarantined:
        errors.append(f"quarantine_nonempty:{quarantined}")

    return {"ok": not errors, "errors": errors, "asset_count": len(assets), "manifest": manifest}


def deterministic_replay() -> dict:
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        ra, rb = Path(a), Path(b)
        va, vb = validate_canary(ra), validate_canary(rb)
        if not va["ok"] or not vb["ok"]:
            return {"ok": False, "errors": va["errors"] + vb["errors"]}
        ma = json.dumps(va["manifest"], sort_keys=True, separators=(",", ":"))
        mb = json.dumps(vb["manifest"], sort_keys=True, separators=(",", ":"))
        if ma != mb:
            return {"ok": False, "errors": ["manifest_replay_mismatch"]}
        return {"ok": True, "asset_count": va["asset_count"], "manifest_sha256": hashlib.sha256(ma.encode()).hexdigest()}


if __name__ == "__main__":
    result = deterministic_replay()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["ok"] else 1)
