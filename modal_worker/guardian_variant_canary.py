"""One-Guardian identity-conditioned canary for the five runtime variants that require new art."""
from __future__ import annotations
import base64, hashlib, io, json, os, time
from pathlib import Path
import modal
from PIL import Image

APP_NAME="freeframe-guardian-variant-canary"; MODEL_ID="black-forest-labs/FLUX.2-klein-4B"; CACHE_DIR="/cache"; MODEL_VOLUME="freeframe-model-cache"
EXTRACTOR_APP="freeframe-worker"; EXTRACTOR_CLASS="FreeFrameExtractor"; STEPS=4; GUIDANCE=1.0
VARIANTS=(
 ("battle-action",192,192,261001,"dynamic forward pounce battle action, energetic readable motion, all four legs anatomically coherent and visible where perspective permits"),
 ("battle-hurt",192,192,261002,"recoiling hurt reaction, defensive lowered posture, ears pulled back, expressive but non-gory, all limbs intact"),
 ("bond-expression",144,144,261003,"warm affectionate bonded expression toward its trusted companion, bright gentle eyes and friendly alert face, calm upright posture"),
 ("field-interaction",192,192,261004,"actively investigating a tiny glowing Thread-magic sprout on the ground, curious natural field interaction, full body readable"),
 ("resting-pose",192,192,261005,"peaceful curled resting pose lying naturally with tail relaxed beside the body, sleepy content expression"),
)
BASE=("Preserve the exact Guardian identity from the supplied accepted master: same fox-like body plan, face, ear shape, tail, orange/cream/dark color placement, woven biological textile integument and proportions. "
      "This is the same living Plushtopia Guardian, not a new fox and not a retail plush toy. One creature only, clean polished 2D fantasy JRPG game art, simple pure white background, no scenery, no text, no border, no extra limbs, no duplicate body parts, no mutation, no clothing or accessories. ")
image=(modal.Image.debian_slim(python_version="3.11").pip_install("accelerate","diffusers","pillow>=10.4,<12","safetensors","sentencepiece","torch>=2.6,<3","transformers").add_local_python_source("modal_worker"))
app=modal.App(APP_NAME); model_cache=modal.Volume.from_name(MODEL_VOLUME,create_if_missing=True)

@app.cls(gpu="L4",image=image,volumes={CACHE_DIR:model_cache},scaledown_window=60,timeout=1200)
class Runner:
 @modal.enter()
 def load(self):
  import torch
  from diffusers import DiffusionPipeline
  os.environ.setdefault("HF_HOME",CACHE_DIR); os.environ.setdefault("HF_HUB_CACHE",f"{CACHE_DIR}/hub")
  self.torch=torch; self.pipe=DiffusionPipeline.from_pretrained(MODEL_ID,torch_dtype=torch.bfloat16,cache_dir=CACHE_DIR).to("cuda")
 @modal.method()
 def run_all(self, master_base64:str):
  reference=Image.open(io.BytesIO(base64.b64decode(master_base64))).convert("RGB"); results=[]
  for name,w,h,seed,pose in VARIANTS:
   gen=self.torch.Generator(device="cuda").manual_seed(seed); started=time.monotonic()
   rendered=self.pipe(image=[reference],prompt=BASE+pose,width=512,height=512,guidance_scale=GUIDANCE,num_inference_steps=STEPS,generator=gen).images[0]
   out=io.BytesIO(); rendered.save(out,format="PNG"); raw=out.getvalue()
   results.append({"name":name,"target":[w,h],"seed":seed,"elapsed_seconds":round(time.monotonic()-started,3),"sha256":hashlib.sha256(raw).hexdigest(),"png_base64":base64.b64encode(raw).decode("ascii")})
  return results

def fit_subject(raw:bytes,w:int,h:int)->bytes:
 im=Image.open(io.BytesIO(raw)).convert("RGBA"); bbox=im.getchannel("A").getbbox()
 if bbox is None: raise RuntimeError("variant extraction has no foreground")
 crop=im.crop(bbox); crop.thumbnail((round(w*.88),round(h*.88)),Image.Resampling.LANCZOS)
 canvas=Image.new("RGBA",(w,h),(0,0,0,0)); canvas.alpha_composite(crop,((w-crop.width)//2,(h-crop.height)//2)); out=io.BytesIO(); canvas.save(out,format="PNG"); return out.getvalue()

@app.local_entrypoint()
def main(master_path:str, guardian_id:int=1):
 raw=Path(master_path).read_bytes(); generated=Runner().run_all.remote(base64.b64encode(raw).decode("ascii")); extractor=modal.Cls.from_name(EXTRACTOR_APP,EXTRACTOR_CLASS)()
 outdir=Path("guardian-variant-canary")/f"guardian-{guardian_id:03d}"; outdir.mkdir(parents=True,exist_ok=True); assets=[]
 for item in generated:
  gen_raw=base64.b64decode(item.pop("png_base64")); (outdir/f"{item['name']}-raw.png").write_bytes(gen_raw)
  ext=extractor.extract.remote({"image_base64":base64.b64encode(gen_raw).decode("ascii")}); ext_raw=base64.b64decode(ext["image_base64"],validate=True)
  w,h=item["target"]; final=fit_subject(ext_raw,w,h); p=outdir/f"{item['name']}.png"; p.write_bytes(final)
  with Image.open(io.BytesIO(final)) as im:
   bbox=im.getchannel("A").getbbox(); valid=im.size==(w,h) and bbox is not None and bbox[0]>0 and bbox[1]>0 and bbox[2]<w and bbox[3]<h
  item.update({"logical_id":f"guardian/guardian-{guardian_id:03d}/{item['name']}","path":str(p),"extraction_provider":ext.get("provider"),"geometry_alpha_valid":valid}); assets.append(item)
 report={"schema":"plushbound.guardian_variant_canary.v1","guardian_id":f"guardian-{guardian_id:03d}","model":MODEL_ID,"variant_count":len(assets),"assets":assets,"production_authorized":False}
 (outdir/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n"); print(json.dumps(report,sort_keys=True))
 if not all(a["geometry_alpha_valid"] for a in assets): raise RuntimeError("Guardian variant canary geometry/alpha failure")
