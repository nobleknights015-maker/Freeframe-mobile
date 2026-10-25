"""Bounded canon portrait batch for Penney, Lily, and Ethan.

This runs only after the Chris portrait canary has cleared the portrait contract.
One production GPU object handles all three requests; outputs remain pending visual
review and are not banked by this module.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path

import modal
from PIL import Image

from modal_worker.canon_portrait_canary import (
    APP_NAME,
    HEIGHT,
    PRODUCTION_MODEL,
    REFERENCE_SCALE,
    RENDERER_ROUTE,
    WIDTH,
    _runtime_transparency,
)

OUTPUT_DIR = Path("canon-portrait-batch")
REPORT = OUTPUT_DIR / "report.json"

CHARACTERS = (
    {
        "character_id": "penney_nguyen",
        "display_name": "Penney Nguyen",
        "descriptor": "adult woman",
        "reference": Path("modal_worker/canon_refs/penney-nguyen_proven.png"),
    },
    {
        "character_id": "lily",
        "display_name": "Lily",
        "descriptor": "teenage girl",
        "reference": Path("modal_worker/canon_refs/lily_proven.png"),
    },
    {
        "character_id": "ethan",
        "display_name": "Ethan",
        "descriptor": "teenage boy",
        "reference": Path("modal_worker/canon_refs/ethan_proven.png"),
    },
)


def _preflight(path: Path) -> tuple[bytes, dict]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError(f"missing proven canon reference: {path}")
    raw = path.read_bytes()
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            width, height = im.size
            mode = im.mode
    except Exception as exc:
        raise ValueError(f"unreadable proven canon reference: {path}") from exc
    if width < 48 or height < 48:
        raise ValueError(f"canon reference too small: {path} {width}x{height}")
    return raw, {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "width": width,
        "height": height,
        "mode": mode,
    }


def _prompt(entry: dict) -> str:
    return (
        f"Canonical Plushbound Legends portrait of {entry['display_name']}, {entry['descriptor']}. "
        "Treat the supplied reference as the authority for character identity: preserve the same face, hair style and color, eye color, "
        "clothing design, palette, accessories, proportions, and overall silhouette. Do not replace those traits with generic fantasy choices. "
        "Polished original Plushbound JRPG illustration with RPG Maker MV cover / Trinity-inspired finish, waist-up three-quarter portrait, "
        "natural confident neutral-to-friendly expression, clean readable silhouette, centered with comfortable headroom. "
        "Pure near-white seamless background for deterministic extraction. Single character only. No text, no UI, no border, no logo, no contact sheet, "
        "no duplicate body parts, no malformed anatomy, hands mostly out of frame."
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    store = modal.Function.from_name(APP_NAME, "store_reference_internal")

    prepared = []
    requests = []
    for entry in CHARACTERS:
        raw, meta = _preflight(entry["reference"])
        stored = store.remote({"image_base64": base64.b64encode(raw).decode("ascii")})
        reference_id = str(stored.get("reference_id") or stored.get("sha256") or stored.get("id") or "").strip()
        if not reference_id:
            raise RuntimeError(f"reference store returned no id for {entry['display_name']}: {stored}")
        seed = int.from_bytes(
            hashlib.sha256(f"plushbound:canon:{entry['character_id']}:portrait:v1".encode()).digest()[:8],
            "big",
        ) & ((1 << 63) - 1)
        prompt = _prompt(entry)
        request = {
            "prompt": prompt,
            "negative_prompt": "",
            "width": WIDTH,
            "height": HEIGHT,
            "steps": 4,
            "guidance_scale": 0.0,
            "seed": seed,
            "renderer_route": RENDERER_ROUTE,
            "model_id": PRODUCTION_MODEL,
            "reference_id": reference_id,
            "reference_mode": "identity",
            "reference_scale": REFERENCE_SCALE,
        }
        prepared.append((entry, meta, reference_id, seed, prompt))
        requests.append(request)

    Generator = modal.Cls.from_name(APP_NAME, "FreeFrameProductionGenerator")
    generator = Generator()
    results = generator.generate_batch.remote(requests)
    if len(results) != len(CHARACTERS):
        raise RuntimeError(f"generator returned {len(results)} results for {len(CHARACTERS)} requests")

    entries = []
    for (entry, ref_meta, reference_id, seed, prompt), result in zip(prepared, results):
        encoded = result.get("image_base64")
        if not encoded:
            raise RuntimeError(f"no image payload for {entry['display_name']}")
        raw_png = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(raw_png)) as im:
            im.load()
            if im.size != (WIDTH, HEIGHT):
                raise ValueError(f"bad geometry for {entry['display_name']}: {im.size}")

        stem = f"{entry['character_id']}_portrait"
        raw_path = OUTPUT_DIR / f"{stem}_raw.png"
        runtime_path = OUTPUT_DIR / f"{stem}.png"
        raw_path.write_bytes(raw_png)
        runtime_png, runtime_meta = _runtime_transparency(raw_png)
        runtime_path.write_bytes(runtime_png)

        entries.append({
            "character_id": entry["character_id"],
            "display_name": entry["display_name"],
            "asset_role": "portrait",
            "status": "generated_pending_visual_review",
            "reference": ref_meta,
            "reference_store": {"reference_id": reference_id, "mode": "identity", "requested_scale": REFERENCE_SCALE},
            "seed": seed,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "renderer": {
                "model": result.get("model"),
                "renderer_route": result.get("renderer_route"),
                "elapsed_seconds": result.get("elapsed_seconds"),
                "output_sha256": result.get("sha256"),
                "output_bytes": result.get("bytes"),
                "reference_conditioning": result.get("reference_conditioning"),
            },
            "runtime_candidate": runtime_meta,
            "quality_gate": {
                "geometry_pass": runtime_meta["width"] == WIDTH and runtime_meta["height"] == HEIGHT,
                "rgba_pass": runtime_meta["mode"] == "RGBA",
                "alpha_present": runtime_meta["transparent_pixels"] > 0,
                "visual_identity_review_required": True,
                "banked": False,
            },
        })

    report = {
        "version": "plushbound-canon-portrait-batch-v1",
        "status": "generated_pending_visual_review",
        "catalog_wide_launch_authorized": False,
        "requested": len(CHARACTERS),
        "completed": len(entries),
        "entries": entries,
    }
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
