"""Three-case confirmation for separated Plushbound style and body conditioning.

Reference 1 is a project-owned non-creature Elyndor style anchor. Reference 2 is the
procedural exterior silhouette guide. This canary tests whether separating those two
responsibilities fixes creature-reference anatomy leakage while restoring Plushtopia
color/render identity. Diagnostic only; never authorizes production.
"""
from __future__ import annotations
import base64, hashlib, io, json, os, time
from pathlib import Path
import modal

APP_NAME="freeframe-noncreature-style-pose-canary"
MODEL_ID="black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR="/cache"; MODEL_VOLUME="freeframe-model-cache"
CANARY_VERSION="noncreature-style-pose-v1"
STEPS=4; GUIDANCE=1.0

CASES=(
 {"case_id":"friendly_quadruped_style_pose","preset":"plushbound_guardian","family":"guardian_friendly","pose_variant":"quadruped","seed":73501,"prompt":"new healthy Elyndor meadow Guardian species with short leaf-shaped ears, four articulated running legs, counterbalancing tail and small glowing seed-shaped brow organ, sprinting naturally, fully enclosed intact exterior body; living matte woven textile integument rather than fur or plush pile; original fantasy species, not a normal animal or toy"},
 {"case_id":"boss_hexapod_style_pose","preset":"plushbound_guardian","family":"guardian_boss","pose_variant":"hexapod","seed":73506,"prompt":"new ancient Elyndor grove Guardian boss, exactly six weight-bearing legs in three separated pairs with all six feet visible, long low fully enclosed torso, root-antler crown, living woven textile integument, localized old surface repairs only, original nonhuman fantasy organism, no visible internal structures"},
 {"case_id":"enemy_hexapod_style_pose","preset":"plushbound_enemy","family":"enemy_creature","pose_variant":"hexapod","seed":73507,"prompt":"new healthy wild Plushtopia thicket predator, exactly six weight-bearing legs in three separated pairs with all six feet visible, long low body, focused predator eyes and digging foreclaws, fully enclosed matte woven textile integument with no fur coat patches repairs collar accessories or exposed interior, feral original species not a pet mascot"},
)

CONTROL=(
 "Two reference images are supplied with separate jobs. Reference image 1 contains only project-owned Elyndor environment art: copy only its polished colorful 2D fantasy JRPG rendering language, outline treatment, painterly shading, material richness, warm storybook lighting and color harmony. Do not copy any building tree shrine prop architecture or object into the creature. "
 "Reference image 2 is only the black exterior body-plan silhouette: obey its outside shape, orientation and externally visible limb count while ignoring its graphic style. "
 "Create one self-propelled living creature in the same world-art presentation quality as reference 1. Its body is solid and fully enclosed; never show skeleton ribs spine skull hollow torso x-ray or cutaway anatomy. "
 "Living textile material is biological integument: matte woven felted or thread-fiber skin conforming to functioning joints and mass. It is not fuzzy synthetic plush pile, ordinary animal fur, stuffed padding, patchwork toy panels, doll construction or retail merchandise. "
 "Eyes are proportionate living eyes, not oversized glossy doll eyes. No collars tags jewelry or pet accessories. No catalog sheet, labels, buildings or props in the final image."
)

image=(modal.Image.debian_slim(python_version="3.11").pip_install("accelerate","diffusers","pillow>=10.4,<12","safetensors","sentencepiece","torch>=2.6,<3","transformers").add_local_python_source("modal_worker").add_local_dir("modal_worker/project_references",remote_path="/root/modal_worker/project_references"))
app=modal.App(APP_NAME); model_cache=modal.Volume.from_name(MODEL_VOLUME,create_if_missing=True)


def request_for(case):
 from modal_worker.production_request_builder import build_production_request
 r=build_production_request(case["preset"],case["prompt"],seed=case["seed"],creature_family=case["family"]); r["steps"]=STEPS; r["guidance_scale"]=GUIDANCE; return r

@app.cls(gpu="L4",image=image,volumes={CACHE_DIR:model_cache},scaledown_window=60,timeout=1200)
class Runner:
 @modal.enter()
 def load(self):
  import torch
  from diffusers import DiffusionPipeline
  os.environ.setdefault("HF_HOME",CACHE_DIR); os.environ.setdefault("HF_HUB_CACHE",f"{CACHE_DIR}/hub")
  self.torch=torch; self.pipe=DiffusionPipeline.from_pretrained(MODEL_ID,torch_dtype=torch.bfloat16,cache_dir=CACHE_DIR).to("cuda")
 @modal.method()
 def run_all(self):
  from modal_worker.creature_pose_guides import POSE_GUIDE_VERSION, build_pose_guide
  from modal_worker.plushbound_style_anchors import get_style_anchor
  anchor=get_style_anchor(); style=anchor.load_image()
  results=[]
  for case in CASES:
   req=request_for(case); pose=build_pose_guide(case["family"],size=512,variant=case["pose_variant"])
   gen=self.torch.Generator(device="cuda").manual_seed(req["seed"]); started=time.monotonic()
   rendered=self.pipe(image=[style,pose],prompt=f"{CONTROL} {req['prompt']}",width=req["width"],height=req["height"],guidance_scale=req["guidance_scale"],num_inference_steps=req["steps"],generator=gen).images[0]
   out=io.BytesIO(); rendered.save(out,format="PNG"); raw=out.getvalue()
   results.append({"canary_version":CANARY_VERSION,"case_id":case["case_id"],"family":case["family"],"pose_guide_version":POSE_GUIDE_VERSION,"style_anchor_id":anchor.anchor_id,"style_anchor_sha256":anchor.sha256,"style_anchor_ownership":anchor.ownership,"creature_policy_version":req["creature_world_policy_version"],"seed":req["seed"],"model":MODEL_ID,"elapsed_seconds":round(time.monotonic()-started,3),"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"production_authorized":False,"png_base64":base64.b64encode(raw).decode("ascii")})
  return results

@app.local_entrypoint()
def main():
 outdir=Path("noncreature-style-pose-canary"); outdir.mkdir(exist_ok=True); results=Runner().run_all.remote(); report={"canary_version":CANARY_VERSION,"count":len(results),"diagnostic":"project_owned_noncreature_style_anchor_plus_exterior_pose","production_authorized":False,"assets":[]}
 for result in results:
  raw=base64.b64decode(result.pop("png_base64")); p=outdir/f"{result['case_id']}.png"; p.write_bytes(raw); result["output_path"]=str(p); report["assets"].append(result)
 (outdir/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True),encoding="utf-8"); print(json.dumps(report,sort_keys=True))
