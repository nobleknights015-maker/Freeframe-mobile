"""Bounded production canary for creator/front-hair/001.

The creator hair family is a transparent overlay family, not a full-character
family. This canary spends five diffusion renders total: one style reference plus
four direction-specific isolated hairpieces. Only the four directional sources are
sent through the deployed BiRefNet extractor. The resulting pieces are normalized
into the shared 48px creator head anchor and repeated across the three walk phases
to produce one exact 144x192 RGBA overlay sheet.
"""
from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path

import modal

APP_NAME = "freeframe-creator-front-hair-canary"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
LOGICAL_ID = "creator/front-hair/001"
STYLE_NAME = "short_side_swept_fringe"
CELL = 48
SHEET_W = 144
SHEET_H = 192
ANCHOR_X = 24
ANCHOR_Y = 1
MAX_HAIR_W = 34
MAX_HAIR_H = 23

DIRECTIONS = (
    ("down", "front-facing view toward the viewer"),
    ("left", "left profile view"),
    ("right", "right profile view"),
    ("up", "rear-facing view showing only the crown/front-layer portion; no long rear-hair layer"),
)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install("accelerate", "diffusers", "pillow>=10.4,<12", "safetensors", "sentencepiece", "torch>=2.6,<3", "transformers")
    .add_local_python_source("modal_worker")
)
app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


def _style_prompt() -> str:
    return (
        "isolated original fantasy JRPG front-hair hairpiece only, short side-swept layered fringe with a compact crown, "
        "clean readable locks, cool graphite-silver neutral hair color suitable for later tinting, polished Plushtopia anime-JRPG rendering, "
        "floating hairpiece with no head, no face, no skin, no ears, no neck, no body, no mannequin, no clothing, no accessories, "
        "no back-hair lengths, one object only, centered on pure white background, no text, no border"
    )


def _direction_prompt(direction_text: str) -> str:
    return (
        "Preserve the exact same hairstyle, lock pattern, silhouette and cool graphite-silver neutral hair color from the reference. "
        f"Render only the isolated front-hair layer as a {direction_text}. "
        "This is a character-creator overlay asset: hair only, no scalp skin, no head, no face, no eyes, no ears, no neck, no body, "
        "no mannequin, no clothing, no accessories, no back-hair lengths, one compact object only, centered on pure white background, "
        "no text, no border. Keep the silhouette compact enough for a 48px RPG character cell."
    )


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=120, timeout=1200)
class CreatorFrontHairCanaryRunner:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import DiffusionPipeline
        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16, cache_dir=CACHE_DIR).to("cuda")

    def _generate(self, prompt: str, seed: int, reference=None):
        generator = self.torch.Generator(device="cuda").manual_seed(seed)
        kwargs = dict(prompt=prompt, width=512, height=512, guidance_scale=1.0, num_inference_steps=4, generator=generator)
        if reference is not None:
            kwargs["image"] = [reference]
        started = time.monotonic()
        result = self.pipe(**kwargs).images[0]
        return result, round(time.monotonic() - started, 3)

    @modal.method()
    def generate(self) -> dict:
        ref_seed = 810100
        reference, ref_seconds = self._generate(_style_prompt(), ref_seed)
        ref_buf = io.BytesIO(); reference.save(ref_buf, format="PNG")
        outputs = []
        for index, (direction, direction_text) in enumerate(DIRECTIONS):
            seed = 810101 + index
            frame, elapsed = self._generate(_direction_prompt(direction_text), seed, reference)
            buf = io.BytesIO(); frame.save(buf, format="PNG")
            outputs.append({
                "direction": direction,
                "seed": seed,
                "seconds": elapsed,
                "png": base64.b64encode(buf.getvalue()).decode("ascii"),
            })
        return {
            "model": MODEL_ID,
            "style_name": STYLE_NAME,
            "reference_seed": ref_seed,
            "reference_seconds": ref_seconds,
            "reference_png": base64.b64encode(ref_buf.getvalue()).decode("ascii"),
            "directions": outputs,
        }


def _extract(encoded: str) -> bytes:
    extractor = modal.Cls.from_name("freeframe-worker", "FreeFrameExtractor")()
    result = extractor.extract.remote({"image_base64": encoded})
    return base64.b64decode(result["image_base64"], validate=True)


def _normalize_piece(payload: bytes):
    from PIL import Image
    with Image.open(io.BytesIO(payload)) as source:
        rgba = source.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        if bbox is None:
            raise RuntimeError("front-hair extraction is empty")
        piece = rgba.crop(bbox)
        w, h = piece.size
        scale = min(MAX_HAIR_W / w, MAX_HAIR_H / h, 1.0)
        if scale < 1.0:
            piece = piece.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.LANCZOS)
        return piece, {"source_bbox": list(bbox), "normalized_size": list(piece.size)}


def _build_sheet(pieces: dict[str, object]):
    from PIL import Image
    sheet = Image.new("RGBA", (SHEET_W, SHEET_H), (0, 0, 0, 0))
    placements = []
    for row, (direction, _) in enumerate(DIRECTIONS):
        piece = pieces[direction]
        for col in range(3):
            x = col * CELL + ANCHOR_X - piece.width // 2
            y = row * CELL + ANCHOR_Y
            sheet.alpha_composite(piece, dest=(x, y))
            placements.append({"direction": direction, "phase_col": col, "x": x, "y": y, "width": piece.width, "height": piece.height})
    return sheet, placements


def _validate_sheet(sheet) -> dict:
    if sheet.mode != "RGBA" or sheet.size != (SHEET_W, SHEET_H):
        raise RuntimeError("front-hair sheet geometry mismatch")
    rows = []
    for row in range(4):
        row_data = []
        for col in range(3):
            cell = sheet.crop((col*CELL, row*CELL, (col+1)*CELL, (row+1)*CELL))
            bbox = cell.getchannel("A").getbbox()
            if bbox is None:
                raise RuntimeError(f"empty front-hair cell row={row} col={col}")
            if bbox[3] > 30:
                raise RuntimeError(f"front-hair layer extends too low in cell row={row} col={col}: {bbox}")
            row_data.append(list(bbox))
        rows.append(row_data)
    return {"passed": True, "cell_bboxes": rows}


@app.local_entrypoint()
def main():
    from PIL import Image
    out_root = Path("creator-front-hair-001-sources")
    out_root.mkdir(parents=True, exist_ok=True)

    remote = CreatorFrontHairCanaryRunner().generate.remote()
    ref = base64.b64decode(remote["reference_png"], validate=True)
    Path("creator-front-hair-001-reference.png").write_bytes(ref)

    pieces = {}
    extraction = []
    for item in remote["directions"]:
        direction = item["direction"]
        raw = base64.b64decode(item["png"], validate=True)
        (out_root / f"{direction}-raw.png").write_bytes(raw)
        cleaned = _extract(item["png"])
        (out_root / f"{direction}-extracted.png").write_bytes(cleaned)
        piece, meta = _normalize_piece(cleaned)
        pieces[direction] = piece
        piece.save(out_root / f"{direction}-normalized.png", format="PNG", optimize=False)
        extraction.append({"direction": direction, "seed": item["seed"], "seconds": item["seconds"], **meta})

    sheet, placements = _build_sheet(pieces)
    validation = _validate_sheet(sheet)
    sheet.save("creator-front-hair-001.png", format="PNG", optimize=False)

    report = {
        "schema": "plushbound.creator_front_hair_canary.v1",
        "logical_id": LOGICAL_ID,
        "style_name": STYLE_NAME,
        "status": "generated_pending_visual_review",
        "model": remote["model"],
        "paid_render_count": 5,
        "paid_extraction_count": 4,
        "source_direction_count": 4,
        "reference_seed": remote["reference_seed"],
        "reference_seconds": remote["reference_seconds"],
        "extraction_backend": "deployed_birefnet",
        "extraction": extraction,
        "head_anchor_contract": {
            "cell_size": CELL,
            "anchor_x": ANCHOR_X,
            "anchor_y": ANCHOR_Y,
            "measured_body_family_top_y": 1,
            "measured_body_family_head_center_mean_x": 23.6528,
            "measured_body_family_head_center_stddev_x": 0.6841,
            "body_count_measured": 24,
        },
        "placements": placements,
        "sheet": {"width": SHEET_W, "height": SHEET_H, "mode": "RGBA", "layout": "3x4-48px"},
        "validation": validation,
        "catalog_wide_launch_authorized": False,
        "next_gate": "visual composite review against locked petite, balanced, and broad creator/body sheets",
    }
    Path("creator-front-hair-001-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"schema": report["schema"], "logical_id": LOGICAL_ID, "renders": 5, "extractions": 4, "validation": validation["passed"]}, sort_keys=True))
