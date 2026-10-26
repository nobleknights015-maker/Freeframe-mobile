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
REFERENCE_IMAGE = Path("modal_worker/project_references/chris_proven_reference.jpg")
REFERENCE_MARKER = Path("modal_worker/project_references/chris_reference_marker.txt")
EXPECTED_REFERENCE_GIT_BLOB = "c69443a17a8120be31685e1820c2271450065493"
OUTPUT_DIR = Path("canon-portrait-canary")
RAW_OUTPUT = OUTPUT_DIR / "chris_bourn_portrait_raw.png"
RUNTIME_OUTPUT = OUTPUT_DIR / "chris_bourn_portrait.png"
REPORT = OUTPUT_DIR / "report.json"
WIDTH = 288
HEIGHT = 384
REFERENCE_SCALE = 0.72
STEPS = 8
GUIDANCE_SCALE = 1.0
SEED = int.from_bytes(hashlib.sha256(b"plushbound:canon:chris_bourn:portrait:v2").digest()[:8], "big") & ((1 << 63) - 1)
PROMPT = (
    "CANONICAL IDENTITY-PRESERVATION REDRAW. Create one 2D anime/JRPG portrait of Chris Bourn for Plushbound Legends. "
    "The supplied reference is the canonical model reference, not loose inspiration. Redraw the same person; do not redesign, beautify, "
    "age-shift, chibify, or simplify him. Preserve facial proportions and structure, eye placement and color, nose and mouth placement, jaw and chin, "
    "hairline, tousled medium-brown hair silhouette and parting, and the overall recognizable face. Preserve the established red scarf/cape accent, "
    "dark layered black-and-deep-red fantasy travel outfit, visible straps, layered construction, armor/guard shapes, trim, and established color blocking. "
    "Render as crisp hand-drawn 2D Japanese-anime-style JRPG key art: clean inked linework, controlled cel shading, restrained painterly accents, matte fabric and leather. "
    "Distinct original Plushbound identity with the polished feel of classic RPG Maker MV/Trinity-era cover illustration, without copying proprietary artwork. "
    "Absolutely no glossy 3D render, CGI, doll, vinyl figure, toy, plastic skin, photorealism, pseudo-3D modeling, or over-smoothed face. "
    "Waist-up three-quarter portrait, calm determined friendly expression, clean readable silhouette, centered with comfortable headroom. "
    "Pure near-white seamless background for deterministic extraction. No text, UI, border, logo, contact sheet, extra people, duplicate body parts, or malformed anatomy; "
    "hands mostly out of frame. This is a single game-ready canonical character portrait source image."
)


def _git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def _preflight_reference() -> tuple[bytes, dict]:
    if not REFERENCE_IMAGE.is_file() or REFERENCE_IMAGE.stat().st_size <= 0:
        raise FileNotFoundError(f"missing canonical reference image: {REFERENCE_IMAGE}")
    if not REFERENCE_MARKER.is_file():
        raise FileNotFoundError(f"missing canonical reference marker: {REFERENCE_MARKER}")

    marker = REFERENCE_MARKER.read_text(encoding="utf-8")
    if "established Plushbound Character Atlas reference" not in marker:
        raise ValueError("Chris reference marker does not identify the established Character Atlas reference")
    if "Do not substitute" not in marker:
        raise ValueError("Chris reference marker does not preserve the no-substitution lock")

    raw = REFERENCE_IMAGE.read_bytes()
    git_blob = _git_blob_sha1(raw)
    if git_blob != EXPECTED_REFERENCE_GIT_BLOB:
        raise ValueError(f"proven Chris reference Git blob changed: {git_blob}")

    try:
        with Image.open(io.BytesIO(raw)) as verify_image:
            verify_image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            source_format = image.format
            source_mode = image.mode
    except Exception as exc:
        raise ValueError("proven Chris reference is not a readable raster image") from exc

    if width < 128 or height < 256:
        raise ValueError(f"proven Chris reference is unexpectedly small: {width}x{height}")
    if source_format != "JPEG":
        raise ValueError(f"unexpected proven Chris reference format: {source_format}")

    return raw, {
        "path": str(REFERENCE_IMAGE),
        "marker_path": str(REFERENCE_MARKER),
        "marker_sha256": hashlib.sha256(REFERENCE_MARKER.read_bytes()).hexdigest(),
        "git_blob_sha1": git_blob,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "width": width,
        "height": height,
        "source_format": source_format,
        "source_mode": source_mode,
        "role": "established_plushbound_character_atlas_identity_reference",
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
    if reference_id != reference_meta["sha256"]:
        raise RuntimeError("reference store id does not match proven reference SHA-256")

    Generator = modal.Cls.from_name(APP_NAME, "FreeFrameProductionGenerator")
    generator = Generator()
    request = {
        "prompt": PROMPT,
        "negative_prompt": "",
        "width": WIDTH,
        "height": HEIGHT,
        "steps": STEPS,
        "guidance_scale": GUIDANCE_SCALE,
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
        "version": "plushbound-canon-portrait-canary-v2",
        "status": "generated_pending_visual_review",
        "character_id": "chris_bourn",
        "display_name": "Chris Bourn",
        "asset_role": "portrait",
        "catalog_wide_launch_authorized": False,
        "retry_reason": "attempt_v1_passed_technical_gate_but_failed_identity_style_and_outfit_visual_gate",
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
