"""Bounded four-case L4 canary for Plushtopia living-textile creature semantics."""
from __future__ import annotations
import base64,hashlib,io,json,os,time
from pathlib import Path
import modal
APP_NAME="freeframe-creature-style-canary"; MODEL_ID="black-forest-labs/FLUX.2-klein-4B"; CACHE_DIR="/cache"; MODEL_VOLUME="freeframe-model-cache"
CANARY_VERSION="living-fabric-creature-canary-v2"; STEPS=4; GUIDANCE=1.0
CASES=(
 {"case_id":"guardian_friendly","preset":"plushbound_guardian","family":"guardian_friendly","seed":73201,"prompt":"small Elyndor meadow Guardian species with long leaf-shaped ears, short muzzle, four agile legs, seed-like glowing brow mark, curious springing posture"},
 {"case_id":"guardian_corrupt","preset":"plushbound_guardian","family":"guardian_corrupt","seed":73202,"prompt":"corrupted woodland Guardian with long leaf-shaped ears, short muzzle and four-legged stalking body plan, matte cloth skin torn by old Thread wounds, roots growing through damaged areas"},
 {"case_id":"guardian_boss","preset":"plushbound_guardian","family":"guardian_boss","seed":73203,"prompt":"ancient Elyndor grove-wader Guardian boss, huge strictly nonhumanoid four-legged creature with broad low torso, four pillar legs, root-crown horns and leaf-shaped ears, guarding a ruined Thread shrine, never bipedal"},
 {"case_id":"enemy_creature","preset":"plushbound_enemy","family":"enemy_creature","seed":73204,"prompt":"feral Plushtopia woodland monster with low long-bodied four-legged anatomy, blunt masklike muzzle, flattened leaflike ears, heavy forepaws and woven textile skin, stalking across an Elyndor clearing"},
)
image=(modal.Image.debian_slim(python_version="3.11").pip_install("accelerate","diffusers","pillow>=10.4,<12","safetensors","sentencepiece","torch>=2.6,<3","transformers").add_local_python_source("modal_worker"))
app=modal.App(APP_NAME); model_cache=modal.Volume.from_name(MODEL_VOLUME,create_if_missing=True)
def request_for(case:dict)->dict:
 from modal_worker.production_request_builder import build_production_request
 request=build_production_request(case["preset"],case["prompt"],seed=int(case["seed"]),creature_family=case["family"]); request["steps"]=STEPS; request["guidance_scale"]=GUIDANCE
 if request["width"]%16 or request["height"]%16: raise ValueError("Klein canary dimensions must be divisible by 16")
 return request
@app.cls(gpu="L4",image=image,volumes={CACHE_DIR:model_cache},scaledown_window=60,timeout=1200)
class CreatureCanaryRunner:
 @modal.enter()
 def load(self):
  import torch
  from diffusers import DiffusionPipeline
  os.environ.setdefault("HF_HOME",CACHE_DIR); os.environ.setdefault("HF_HUB_CACHE",f"{CACHE_DIR}/hub"); self.torch=torch
  self.pipe=DiffusionPipeline.from_pretrained(MODEL_ID,torch_dtype=torch.bfloat16,cache_dir=CACHE_DIR); self.pipe.to("cuda")
 @modal.method()
 def run_all(self)->list[dict]:
  results=[]
  for case in CASES:
   request=request_for(case); generator=self.torch.Generator(device="cuda").manual_seed(int(request["seed"])); started=time.monotonic()
   rendered=self.pipe(prompt=str(request["prompt"]),width=int(request["width"]),height=int(request["height"]),guidance_scale=float(request["guidance_scale"]),num_inference_steps=int(request["steps"]),generator=generator).images[0]
   elapsed=round(time.monotonic()-started,3); out=io.BytesIO(); rendered.save(out,format="PNG"); raw=out.getvalue()
   results.append({"canary_version":CANARY_VERSION,"case_id":case["case_id"],"preset":case["preset"],"creature_family":request["creature_family"],"creature_world_policy_version":request["creature_world_policy_version"],"guardian_composition_family":request.get("guardian_composition_family"),"style_profile":request["production_style_profile"],"request_builder_version":request["production_request_builder_version"],"model":MODEL_ID,"gpu":"L4","elapsed_seconds":elapsed,"seed":int(request["seed"]),"width":rendered.width,"height":rendered.height,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"production_authorized":False,"png_base64":base64.b64encode(raw).decode("ascii")})
  return results
@app.local_entrypoint()
def main():
 output_dir=Path("creature-style-canary"); output_dir.mkdir(exist_ok=True); results=CreatureCanaryRunner().run_all.remote(); report={"canary_version":CANARY_VERSION,"count":len(results),"production_authorized":False,"assets":[]}
 for result in results:
  raw=base64.b64decode(result.pop("png_base64")); p=output_dir/f"{result['case_id']}.png"; p.write_bytes(raw); result["output_path"]=str(p); report["assets"].append(result)
 (output_dir/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True),encoding="utf-8"); print(json.dumps(report,sort_keys=True))
