"""Bounded L4 semantic canary for living-textile creature art direction.

Reference image 1 carries project-owned Plushbound render/material language. Reference
image 2 is a procedural anatomy silhouette. Seven cases deliberately cover diverse
healthy Guardian anatomy plus corruption, boss scale and a hostile wild monster.
Nothing in this canary authorizes catalog production.
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
CANARY_VERSION = "project-reference-pose-canary-v2-organism-first"
STEPS = 4
GUIDANCE = 1.0

CASES = (
    {
        "case_id": "guardian_friendly_quadruped",
        "preset": "plushbound_guardian",
        "family": "guardian_friendly",
        "pose_variant": "quadruped",
        "seed": 73501,
        "prompt": "new healthy Elyndor meadow Guardian species with short leaf-shaped ears, four articulated running legs, a counterbalancing tail and a small glowing seed-shaped brow organ, sprinting naturally along a path, intact skin with no repairs or wounds",
    },
    {
        "case_id": "guardian_friendly_winged",
        "preset": "plushbound_guardian",
        "family": "guardian_friendly",
        "pose_variant": "winged",
        "seed": 73502,
        "prompt": "new healthy Elyndor winged Guardian species with two broad living textile wings, two grasping feet, a compact aerodynamic body, antenna-like thread sensory crests and luminous pollen markings, banking through a sunny grove, intact skin with no repairs or wounds",
    },
    {
        "case_id": "guardian_friendly_biped",
        "preset": "plushbound_guardian",
        "family": "guardian_friendly",
        "pose_variant": "biped",
        "seed": 73503,
        "prompt": "new healthy Elyndor small bipedal Guardian species with two digitigrade jumping legs, tiny nonhuman forelimbs, a long counterbalancing tail and reed-like sensory crest, hopping over stones with alert natural posture, intact skin with no repairs or wounds",
    },
    {
        "case_id": "guardian_friendly_long_low",
        "preset": "plushbound_guardian",
        "family": "guardian_friendly",
        "pose_variant": "long_low",
        "seed": 73504,
        "prompt": "new healthy Brooktail-like river Guardian species with a long flexible low torso, four short articulated legs, broad steering tail and flowing thread-fin crest, bounding beside shallow water, intact skin with no repairs or wounds",
    },
    {
        "case_id": "guardian_corrupt_low",
        "preset": "plushbound_guardian",
        "family": "guardian_corrupt",
        "pose_variant": "low_quadruped",
        "seed": 73505,
        "prompt": "new corrupted woodland Guardian species with a broad leaf tail, functional low quadruped anatomy, a few localized old seam wounds exposing pale inner fibers, moss and roots growing only through damaged areas, prowling under corrupted Thread influence",
    },
    {
        "case_id": "guardian_boss_hexapod",
        "preset": "plushbound_guardian",
        "family": "guardian_boss",
        "pose_variant": "hexapod",
        "seed": 73506,
        "prompt": "new ancient Elyndor grove Guardian boss with exactly three clearly separated pairs of weight-bearing legs, six distinct feet visible, a long low torso, root-antler crown, localized layered old repairs and corrupted Thread wounds, advancing heavily while guarding a ruined shrine",
    },
    {
        "case_id": "enemy_creature_hexapod",
        "preset": "plushbound_enemy",
        "family": "enemy_creature",
        "pose_variant": "hexapod",
        "seed": 73507,
        "prompt": "new healthy wild Plushtopia thicket predator with exactly three clearly separated pairs of legs, six distinct feet, a long low body, narrow focused predator eyes, blunt armored face and oversized digging foreclaws, stalking with tense weight-bearing posture, intact textile integument with no repairs wounds patches or exposed filling",
    },
)

REFERENCE_CONTROL = (
    "Two reference images are supplied. Reference image 1 is project-owned Plushbound art direction: use only its polished 2D fantasy JRPG rendering, color harmony and living-textile material vocabulary; create a different original species and do not inherit its exact body proportions, repair marks, pose or toy-like construction. "
    "Reference image 2 is a strict black silhouette anatomy guide: obey its body orientation, broad proportions and limb count while ignoring its black-and-white graphic style. "
    "The subject is a self-propelled living organism, not an object brought to life. Build the silhouette from functional skeleton, joints, weight and locomotion first; let textile qualities appear only as living integument conforming over that anatomy. "
    "Do not use inflated padding, tubular stuffed limbs, oversized baby head, glossy doll eyes, round mascot muzzle, sewing-pattern panel borders or decorative repair stitches on healthy creatures. "
    "Do not show a store-bought plush toy, stuffed animal, doll, merchandise product, mascot suit, product-photo staging, ordinary flesh-and-fur animal, human torso, gorilla or werewolf. Keep one clearly 2D illustrated creature acting naturally inside the game world."
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
            pose_reference = build_pose_guide(
                case["family"], size=512, variant=case.get("pose_variant")
            )
            prompt = f"{REFERENCE_CONTROL} {request['prompt']}"
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
                    "pose_variant": case.get("pose_variant"),
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
