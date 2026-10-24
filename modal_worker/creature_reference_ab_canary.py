"""Three-case diagnostic: pose-only conditioning versus existing creature style refs.

Uses the same seeds/body-plan intents as the rejected v3 canary, but deliberately
removes the creature style crop. This isolates whether the project-owned creature
reference is causing plush-toy / ordinary-animal drift. Diagnostic only.
"""
from __future__ import annotations
import base64, hashlib, io, json, os, time
from pathlib import Path
import modal

APP_NAME="freeframe-creature-reference-ab-canary"
MODEL_ID="black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR="/cache"; MODEL_VOLUME="freeframe-model-cache"
CANARY_VERSION="creature-reference-ab-v1-pose-only"
STEPS=4; GUIDANCE=1.0

CASES=(
 {"case_id":"friendly_quadruped_pose_only","preset":"plushbound_guardian","family":"guardian_friendly","pose_variant":"quadruped","seed":73501,"prompt":"new healthy Elyndor meadow Guardian species with short leaf-shaped ears, four articulated running legs, counterbalancing tail and small glowing seed-shaped brow organ, sprinting naturally, fully enclosed intact exterior body; living matte woven textile integument rather than fur or plush pile; original fantasy species, not a normal animal or toy"},
 {"case_id":"boss_hexapod_pose_only","preset":"plushbound_guardian","family":"guardian_boss","pose_variant":"hexapod","seed":73506,"prompt":"new ancient Elyndor grove Guardian boss, exactly six weight-bearing legs in three separated pairs with all six feet visible, long low fully enclosed torso, root-antler crown, living woven textile integument, localized old surface repairs only, original nonhuman fantasy organism, no visible internal structures"},
 {"case_id":"enemy_hexapod_pose_only","preset":"plushbound_enemy","family":"enemy_creature","pose_variant":"hexapod","seed":73507,"prompt":"new healthy wild Plushtopia thicket predator, exactly six weight-bearing legs in three separated pairs with all six feet visible, long low body, focused predator eyes and digging foreclaws, fully enclosed matte woven textile integument with no fur coat patches repairs collar accessories or exposed interior, feral original species not a pet mascot"},
)

CONTROL=(
 "One reference image is supplied. It is a strict black exterior silhouette body-plan guide only. Obey its outside shape, orientation and visible limb count while ignoring its black graphic style. "
 "Create polished 2D fantasy JRPG creature art in-world, with painterly illustrated lighting rather than product photography. "
 "The organism has a solid fully enclosed body; never show bones ribs spine skull hollow torso x-ray or cutaway anatomy. "
 "Living textile material must read as matte woven felted thread-fiber biological integument, not fuzzy synthetic plush pile, normal fur, stuffed padding, patchwork toy panels, doll construction or retail merchandise. "
 "Eyes must be proportionate living eyes, not oversized glossy doll eyes. No collars jewelry tags or pet accessories unless explicitly requested."
)

image=(modal.Image.debian_slim(python_version="3.11").pip_install("accelerate","diffusers","pillow>=10.4,<12","safetensors","sentencepiece","torch>=2.6,<3","transformers").add_local_python_source("modal_worker"))
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
  results=[]
  for case in CASES:
   req=request_for(case); pose=build_pose_guide(case["family"],size=512,variant=case["pose_variant"])
   gen=self.torch.Generator(device="cuda").manual_seed(req["seed"]); started=time.monotonic()
   rendered=self.pipe(image=pose,prompt=f"{CONTROL} {req['prompt']}",width=req["width"],height=req["height"],guidance_scale=req["guidance_scale"],num_inference_steps=req["steps"],generator=gen).images[0]
   out=io.BytesIO(); rendered.save(out,format="PNG"); raw=out.getvalue()
   results.append({"canary_version":CANARY_VERSION,"case_id":case["case_id"],"family":case["family"],"pose_guide_version":POSE_GUIDE_VERSION,"creature_policy_version":req["creature_world_policy_version"],"seed":req["seed"],"model":MODEL_ID,"elapsed_seconds":round(time.monotonic()-started,3),"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"production_authorized":False,"png_base64":base64.b64encode(raw).decode("ascii")})
  return results

@app.local_entrypoint()
def main():
 outdir=Path("creature-reference-ab-canary"); outdir.mkdir(exist_ok=True); results=Runner().run_all.remote(); report={"canary_version":CANARY_VERSION,"count":len(results),"diagnostic":"pose_only_no_creature_style_reference","production_authorized":False,"assets":[]}
 for result in results:
  raw=base64.b64decode(result.pop("png_base64")); p=outdir/f"{result['case_id']}.png"; p.write_bytes(raw); result["output_path"]=str(p); report["assets"].append(result)
 (outdir/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True),encoding="utf-8"); print(json.dumps(report,sort_keys=True))
