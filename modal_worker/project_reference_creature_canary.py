"""Reference-conditioned L4 canary for Plushbound living-textile creature families.

This is intentionally separate from creature_style_canary.py so text-only v2 remains
preserved as comparison evidence. Each case uses one hash-verified project-owned,
text-free crop as visual conditioning plus the same deterministic family contract
used by Mini-Jarvis and production planning.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import time
from pathlib import Path

import modal

APP_NAME = "freeframe-project-reference-creature-canary"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
CANARY_VERSION = "project-reference-creature-canary-v1"
STEPS = 4
GUIDANCE = 1.0

CASES = (
    {
        "case_id": "guardian_friendly_reference",
        "preset": "plushbound_guardian",
        "family": "guardian_friendly",
        "seed": 73301,
        "prompt": (
            "Design a new Elyndor Guardian species unlike the reference creature: a small four-legged meadow runner with rounded leaf fins "
            "along its cheeks, short ears, padded feet and a bright seed-shaped brow mark, caught mid-step and clearly alive"
        ),
    },
    {
        "case_id": "guardian_corrupt_reference",
        "preset": "plushbound_guardian",
        "family": "guardian_corrupt",
        "seed": 73302,
        "prompt": (
            "Design a new corrupted woodland Guardian species unlike the reference creature: low four-legged body, broad leaf-shaped tail, "
            "woven textile skin split by old Thread wounds exposing pale tangled fibers, roots and moss growing through damaged areas"
        ),
    },
    {
        "case_id": "guardian_boss_reference",
        "preset": "plushbound_guardian",
        "family": "guardian_boss",
        "seed": 73303,
        "prompt": (
            "Design a new ancient Elyndor Guardian boss unlike the reference creature: enormous strictly nonhumanoid six-legged grove beast, "
            "long low torso, tree-root antlers, heavy woven textile hide, old repairs and torn fiber wounds, guarding a ruined Thread shrine"
        ),
    },
    {
        "case_id": "enemy_creature_reference",
        "preset": "plushbound_enemy",
        "family": "enemy_creature",
        "seed": 73304,
        "prompt": (
            "Design a new wild Plushtopia monster unlike the reference creature: low long-bodied six-legged thicket predator with a blunt masklike face, "
            "woven quilted biological hide, sparse thread bristles and oversized digging foreclaws stalking through an Elyndor clearing"
        ),
    },
)

REFERENCE_INSTRUCTION = (
    "Use the supplied project-owned reference only for Plushbound art direction, material language, creature-to-textile balance, rendering finish and world identity. "
    "Create a different original species with the anatomy described in the prompt. Do not copy the source creature's exact silhouette, markings, pose or proportions. "
    "Do not reproduce any contact-sheet layout, labels, typography, UI, captions, borders or product presentation. "
    "The result must be one living in-world creature, not a toy, doll, merchandise item, ordinary furry animal or mascot."
)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "accelerate",
        "diffusers",
        "pillow>=10.4,<12",
        "safetensors",
        "sentencepiece",
        "torch>=2.6,<3",
        "transformers",
    )
    .add_local_python_source("modal_worker")
    .add_local_dir(
        "modal_worker/project_references",
        remote_path="/root/modal_worker/project_references",
    )
)
app = modal.App(APP_NAME)
model_cache = modal.Volume.from_name(MODEL_VOLUME, create_if_missing=True)


def request_for(case: dict) -> dict:
    from modal_worker.production_request_builder import build_production_request

    request = build_production_request(
        case["preset"],
        case["prompt"],
        seed=int(case["seed"]),
        creature_family=case["family"],
    )
    request["steps"] = STEPS
    request["guidance_scale"] = GUIDANCE
    if request["width"] % 16 or request["height"] % 16:
        raise ValueError("Klein canary dimensions must be divisible by 16")
    return request


@app.cls(
    gpu="L4",
    image=image,
    volumes={CACHE_DIR: model_cache},
    scaledown_window=60,
    timeout=1200,
)
class ProjectReferenceCreatureCanaryRunner:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import DiffusionPipeline

        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
            cache_dir=CACHE_DIR,
        )
        self.pipe.to("cuda")

    @modal.method()
    def run_all(self) -> list[dict]:
        from modal_worker.plushbound_project_references import get_project_reference

        results = []
        for case in CASES:
            request = request_for(case)
            project_reference = get_project_reference(case["family"])
            reference_image = project_reference.load_image()
            # Upscale the small conditioning crop without inventing new pixels. This
            # gives the image encoder enough spatial signal while preserving the
            # project-owned source crop exactly as the provenance anchor.
            reference_image = reference_image.resize((512, 512))
            prompt = f"{REFERENCE_INSTRUCTION} {request['prompt']}"
            generator = self.torch.Generator(device="cuda").manual_seed(int(request["seed"]))
            started = time.monotonic()
            rendered = self.pipe(
                image=reference_image,
                prompt=prompt,
                width=int(request["width"]),
                height=int(request["height"]),
                guidance_scale=float(request["guidance_scale"]),
                num_inference_steps=int(request["steps"]),
                generator=generator,
            ).images[0]
            elapsed = round(time.monotonic() - started, 3)
            out = io.BytesIO()
            rendered.save(out, format="PNG")
            raw = out.getvalue()
            results.append(
                {
                    "canary_version": CANARY_VERSION,
                    "case_id": case["case_id"],
                    "preset": case["preset"],
                    "creature_family": request["creature_family"],
                    "creature_world_policy_version": request["creature_world_policy_version"],
                    "guardian_composition_family": request.get("guardian_composition_family"),
                    "style_profile": request["production_style_profile"],
                    "request_builder_version": request["production_request_builder_version"],
                    "reference_library_version": project_reference.metadata()["library_version"],
                    "reference_id": project_reference.reference_id,
                    "reference_sha256": project_reference.sha256,
                    "reference_source_sheet_sha256": project_reference.source_sheet_sha256,
                    "reference_ownership": project_reference.ownership,
                    "reference_purpose": project_reference.purpose,
                    "model": MODEL_ID,
                    "gpu": "L4",
                    "elapsed_seconds": elapsed,
                    "seed": int(request["seed"]),
                    "width": rendered.width,
                    "height": rendered.height,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                    "production_authorized": False,
                    "png_base64": base64.b64encode(raw).decode("ascii"),
                }
            )
        return results


@app.local_entrypoint()
def main():
    output_dir = Path("project-reference-creature-canary")
    output_dir.mkdir(exist_ok=True)
    results = ProjectReferenceCreatureCanaryRunner().run_all.remote()
    report = {
        "canary_version": CANARY_VERSION,
        "count": len(results),
        "production_authorized": False,
        "assets": [],
    }
    for result in results:
        raw = base64.b64decode(result.pop("png_base64"))
        output_path = output_dir / f"{result['case_id']}.png"
        output_path.write_bytes(raw)
        result["output_path"] = str(output_path)
        report["assets"].append(result)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
