"""Bounded canonical portrait identity canary for Plushbound Legends.

One paid render only. The catalog-wide canon portrait family remains locked until
this artifact is inspected and explicitly banked by the production coordinator.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
from collections import deque
from pathlib import Path

import modal
from PIL import Image

APP_NAME = "freeframe-worker"
PRODUCTION_MODEL = "black-forest-labs/FLUX.2-klein-4B"
RENDERER_ROUTE = "flux2_klein"
REFERENCE_B64 = Path("modal_worker/canon_refs/chris_identity_compact.b64")
REFERENCE_PROVENANCE = Path("modal_worker/canon_refs/chris_identity_provenance.json")
OUTPUT_DIR = Path("canon-portrait-canary")
RAW_OUTPUT = OUTPUT_DIR / "chris_bourn_portrait_raw.png"
RUNTIME_OUTPUT = OUTPUT_DIR / "chris_bourn_portrait.png"
REPORT = OUTPUT_DIR / "report.json"
WIDTH = 288
HEIGHT = 384
REFERENCE_SCALE = 0.72
SEED = int.from_bytes(hashlib.sha256(b"plushbound:canon:chris_bourn:portrait:v1").digest()[:8], "big") & ((1 << 63) - 1)
PROMPT = (
    "Canonical Plushbound Legends portrait of Chris Bourn, adult male. Preserve the supplied reference identity exactly: "
    "same brown hair, blue eyes, facial identity, red scarf or hooded-cape accent, dark layered fantasy outfit, established colors, "
    "and compact heroic proportions. Polished original Plushbound JRPG illustration with RPG Maker MV cover / Trinity-inspired finish, "
    "waist-up three-quarter portrait, calm determined friendly expression, clean readable silhouette, centered with comfortable headroom. "
    "Pure near-white seamless background for deterministic extraction. No text, no UI, no border, no logo, no contact sheet, no extra people, "
    "no duplicate body parts, no malformed anatomy, hands mostly out of frame. This is a single game-ready character portrait source image."
)


def _preflight_reference() -> tuple[bytes, dict]:
    if not REFERENCE_B64.is_file() or REFERENCE_B64.stat().st_size <= 0:
        raise FileNotFoundError(f"missing canonical reference payload: {REFERENCE_B64}")
    if not REFERENCE_PROVENANCE.is_file():
        raise FileNotFoundError(f"missing canonical reference provenance: {REFERENCE_PROVENANCE}")

    provenance = json.loads(REFERENCE_PROVENANCE.read_text(encoding="utf-8"))
    if provenance.get("schema") != "plushbound.canon_identity_reference.v1":
        raise ValueError("unexpected Chris reference provenance schema")
    if provenance.get("character_id") != "chris_bourn":
        raise ValueError("Chris reference provenance character mismatch")
    if provenance.get("status") != "CANONICAL_CONDITIONING_REFERENCE":
        raise ValueError("Chris reference is not marked canonical conditioning reference")
    if provenance.get("catalog_wide_launch_authorized") is not False:
        raise ValueError("reference provenance must keep catalog-wide launch disabled")

    encoded = "".join(REFERENCE_B64.read_text(encoding="ascii").split())
    expected = provenance["encoded_payload"]
    if len(encoded) != int(expected["base64_characters"]):
        raise ValueError(f"canonical reference base64 length mismatch: {len(encoded)}")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("canonical Chris reference payload is not valid base64") from exc

    actual_sha = hashlib.sha256(raw).hexdigest()
    if len(raw) != int(expected["decoded_bytes"]):
        raise ValueError(f"canonical reference decoded byte count mismatch: {len(raw)}")
    if actual_sha != expected["decoded_sha256"]:
        raise ValueError(f"canonical reference SHA-256 mismatch: {actual_sha}")

    try:
        with Image.open(io.BytesIO(raw)) as verify_image:
            verify_image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            source_format = image.format
    except Exception as exc:
        raise ValueError("canonical Chris reference payload is not a readable raster image") from exc

    if [width, height] != [int(expected["decoded_width"]), int(expected["decoded_height"])]:
        raise ValueError(f"canonical reference geometry mismatch: {width}x{height}")
    if source_format != expected["decoded_format"]:
        raise ValueError(f"canonical reference format mismatch: {source_format}")
    if width < 64 or height < 64:
        raise ValueError(f"canonical reference is too small: {width}x{height}")

    provenance_sha = hashlib.sha256(REFERENCE_PROVENANCE.read_bytes()).hexdigest()
    return raw, {
        "path": str(REFERENCE_B64),
        "provenance_path": str(REFERENCE_PROVENANCE),
        "provenance_sha256": provenance_sha,
        "source_library_file_id": provenance["source"]["file_id"],
        "source_library_sha256": provenance["source"]["sha256"],
        "derivation": provenance["derivation"],
        "encoding": "base64",
        "decoded_bytes": len(raw),
        "sha256": actual_sha,
        "width": width,
        "height": height,
        "source_format": source_format,
    }


def _runtime_transparency(raw_png: bytes) -> tuple[bytes, dict]:
    """Remove only edge-connected near-white background pixels."""
    with Image.open(io.BytesIO(raw_png)) as source:
        image = source.convert("RGBA")
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f"unexpected portrait geometry: {image.size}")

    pixels = image.load()
    visited = bytearray(WIDTH * HEIGHT)
    q: deque[tuple[int, int]] = deque()

    def push(x: int, y: int) -> None:
        idx = y * WIDTH + x
        if visited[idx]:
            return
        visited[idx] = 1
        r, g, b, _ = pixels[x, y]
        if min(r, g, b) >= 242 and max(r, g, b) - min(r, g, b) <= 18:
            q.append((x, y))

    for x in range(WIDTH):
        push(x, 0)
        push(x, HEIGHT - 1)
    for y in range(HEIGHT):
        push(0, y)
        push(WIDTH - 1, y)

    removed = 0
    while q:
        x, y = q.popleft()
        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        removed += 1
        if x > 0:
            push(x - 1, y)
        if x + 1 < WIDTH:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < HEIGHT:
            push(x, y + 1)

    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("deterministic extraction removed the entire portrait")
    if removed == 0:
        raise ValueError("no edge-connected near-white background was found; portrait requires review")

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    data = out.getvalue()
    return data, {
        "width": WIDTH,
        "height": HEIGHT,
        "mode": "RGBA",
        "alpha_bbox": list(bbox),
        "transparent_pixels": removed,
        "transparent_fraction": round(removed / float(WIDTH * HEIGHT), 6),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reference_raw, reference_meta = _preflight_reference()

    store = modal.Function.from_name(APP_NAME, "store_reference_internal")
    stored = store.remote({"image_base64": base64.b64encode(reference_raw).decode("ascii")})
    reference_id = str(stored.get("reference_id") or stored.get("sha256") or stored.get("id") or "").strip()
    if not reference_id:
        raise RuntimeError(f"reference store did not return an id: {stored}")

    Generator = modal.Cls.from_name(APP_NAME, "FreeFrameProductionGenerator")
    generator = Generator()
    request = {
        "prompt": PROMPT,
        "negative_prompt": "",
        "width": WIDTH,
        "height": HEIGHT,
        "steps": 4,
        "guidance_scale": 0.0,
        "seed": SEED,
        "renderer_route": RENDERER_ROUTE,
        "model_id": PRODUCTION_MODEL,
        "reference_id": reference_id,
        "reference_mode": "identity",
        "reference_scale": REFERENCE_SCALE,
    }
    result = generator.generate.remote(request)
    encoded = result.get("image_base64")
    if not encoded:
        raise RuntimeError("production generator returned no image payload")
    raw_png = base64.b64decode(encoded, validate=True)
    with Image.open(io.BytesIO(raw_png)) as rendered:
        rendered.load()
        if rendered.size != (WIDTH, HEIGHT):
            raise ValueError(f"renderer returned {rendered.size}, expected {(WIDTH, HEIGHT)}")
    RAW_OUTPUT.write_bytes(raw_png)

    runtime_png, runtime_meta = _runtime_transparency(raw_png)
    RUNTIME_OUTPUT.write_bytes(runtime_png)

    report = {
        "version": "plushbound-canon-portrait-canary-v1",
        "status": "generated_pending_visual_review",
        "character_id": "chris_bourn",
        "display_name": "Chris Bourn",
        "asset_role": "portrait",
        "catalog_wide_launch_authorized": False,
        "reference": reference_meta,
        "reference_store": {"reference_id": reference_id, "requested_scale": REFERENCE_SCALE, "mode": "identity"},
        "request": {k: v for k, v in request.items() if k != "prompt"},
        "prompt_sha256": hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
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
    }
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
