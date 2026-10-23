"""Two-reference L4 canary: project visual bible + procedural anatomy guide.

Image 1 carries Plushbound art/material language. Image 2 carries only body layout.
The experiment tests whether splitting style and anatomy control solves the remaining
friendly-toy and boss-humanoid drift seen in earlier canaries.
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

APP_NAME = "freeframe-project-reference-pose-canary"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR = "/cache"
MODEL_VOLUME = "freeframe-model-cache"
CANARY_VERSION = "project-reference-pose-canary-v1"
STEPS = 4
GUIDANCE = 1.0

CASES = (
    {
        "case_id": "guardian_friendly_style_pose",
        "preset": "plushbound_guardian",
        "family": "guardian_friendly",
        "seed": 73401,
        "prompt": "new Elyndor meadow Guardian with short rounded ears, leaf-like cheek fins, padded paws and a glowing seed-shaped brow mark, running happily along a path",
    },
    {
        "case_id": "guardian_corrupt_style_pose",
        "preset": "plushbound_guardian",
        "family": "guardian_corrupt",
        "seed": 73402,
        "prompt": "new corrupted woodland Guardian with broad leaf tail, old seam wounds exposing pale inner fibers, moss and roots growing through damaged fabric-like living tissue, prowling low to the ground",
    },
    {
        "case_id": "guardian_boss_style_pose",
        "preset": "plushbound_guardian",
        "family": "guardian_boss",
        "seed": 73403,
        "prompt": "new ancient Elyndor grove Guardian boss with six weight-bearing legs, a long low torso, root-antler crown, layered old repairs and corrupted Thread wounds, guarding a ruined shrine",
    },
    {
        "case_id": "enemy_creature_style_pose",
        "preset": "plushbound_enemy",
        "family": "enemy_creature",
        "seed": 73404,
        "prompt": "new wild Plushtopia thicket predator with six legs, long low body, blunt mask-like face, oversized digging foreclaws, patches and sparse thread bristles, stalking through an Elyndor clearing",
    },
)

CONTROL_INSTRUCTION = (
    "There are two reference images. Reference image 1 is project-owned Plushbound visual art direction only: follow its polished 2D fantasy JRPG illustration language, soft plush-inspired creature design, color treatment and handcrafted world identity, but create a different original species. "
    "Reference image 2 is a strict black silhouette anatomy guide only: follow its horizontal body plan, limb count, grounded stance and nonhuman proportions, but do not copy its black-and-white graphic style. "
    "Render one living animated fantasy creature in the game world. Plush/fabric qualities should read through soft padded body volumes, subtle stitched seams, patches, thread tufts and exposed stuffing-like fibers where damaged. "
    "Do not render literal burlap weave, photoreal cloth macro texture, realistic animal fur, a store-bought plush toy, doll, merchandise product, mascot suit, human torso, bodybuilder, gorilla or werewolf. "
    "Keep the result clearly 2D illustrated and game-art-like rather than a photographed physical object."
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


def _upscale_preserving_aspect(image, max_edge: int = 512):
    from PIL import Image

    width, height = image.size
    scale = max_edge / float(max(width, height))
    if scale <= 1.0:
        return image
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def request_for(case: dict) -> dict:
    from modal_worker.production_request_builder import build_production_request

    request = build_production_request(
        case["preset"], case["prompt"], seed=int(case["seed"]), creature_family=case["family"]
    )
    request["steps"] = STEPS
    request["guidance_scale"] = GUIDANCE
    return request


@app.cls(gpu="L4", image=image, volumes={CACHE_DIR: model_cache}, scaledown_window=60, timeout=1200)
class ProjectReferencePoseCanaryRunner:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import DiffusionPipeline

        os.environ.setdefault("HF_HOME", CACHE_DIR)
        os.environ.setdefault("HF_HUB_CACHE", f"{CACHE_DIR}/hub")
        self.torch = torch
        self.pipe = DiffusionPipeline.from_pretrained(
            MODEL_ID, torch_dtype=torch.bfloat16, cache_dir=CACHE_DIR
        )
        self.pipe.to("cuda")

    @modal.method()
    def run_all(self) -> list[dict]:
        from modal_worker.creature_pose_guides import POSE_GUIDE_VERSION, build_pose_guide
        from modal_worker.plushbound_project_references import get_project_reference

        results = []
        for case in CASES:
            request = request_for(case)
            project_reference = get_project_reference(case["family"])
            style_reference = _upscale_preserving_aspect(project_reference.load_image())
            pose_reference = build_pose_guide(case["family"], size=512)
            prompt = f"{CONTROL_INSTRUCTION} {request['prompt']}"
            generator = self.torch.Generator(device="cuda").manual_seed(int(request["seed"]))
            started = time.monotonic()
            rendered = self.pipe(
                image=[style_reference, pose_reference],
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
                    "family": case["family"],
                    "pose_guide_version": POSE_GUIDE_VERSION,
                    "reference_library_version": project_reference.metadata()["library_version"],
                    "reference_sha256": project_reference.sha256,
                    "reference_ownership": project_reference.ownership,
                    "request_builder_version": request["production_request_builder_version"],
                    "creature_policy_version": request["creature_world_policy_version"],
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
    output_dir = Path("project-reference-pose-canary")
    output_dir.mkdir(exist_ok=True)
    results = ProjectReferencePoseCanaryRunner().run_all.remote()
    report = {"canary_version": CANARY_VERSION, "count": len(results), "production_authorized": False, "assets": []}
    for result in results:
        raw = base64.b64decode(result.pop("png_base64"))
        output_path = output_dir / f"{result['case_id']}.png"
        output_path.write_bytes(raw)
        result["output_path"] = str(output_path)
        report["assets"].append(result)
    (output_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
