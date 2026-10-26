"""All-96 Guardian production for selectable runtime variants that require new visual art.

One accepted Guardian master is the strict identity reference. A production wave may select
one or more of the frozen purpose-specific FLUX.2 Klein variant roles. Semantic subject
extraction is used for normal creature-only roles; field-interaction uses deterministic
near-white alpha removal so its interaction prop is preserved. Exact frozen runtime geometry
is applied locally. Physical GPU overlap is bounded by the caller to <=4 Guardian lanes,
keeping generator+extractor overlap <=8.
"""
from __future__ import annotations

import base64, hashlib, io, json, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import modal

APP_NAME="freeframe-guardian-variant-production"
MODEL_ID="black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR="/cache"; MODEL_VOLUME="freeframe-model-cache"
EXTRACTOR_APP="freeframe-worker"; EXTRACTOR_CLASS="FreeFrameExtractor"
GPU_SECOND_COST_USD=0.000222
MAX_PARALLEL_LANES=4
OUT_ROOT=Path("guardian-variant-production")
VARIANTS=(
 ("battle-action",192,192,"dynamic battle action appropriate to this creature's existing anatomy and natural locomotion, strong forward motion, exact original limb and wing count preserved"),
 ("battle-hurt",192,192,"clear hurt recoil reaction, defensive lowered or withdrawn posture appropriate to its anatomy, expressive but non-gory, every original limb and body part intact"),
 ("bond-expression",144,144,"warm affectionate bonded expression toward its trusted companion, gentle bright expression appropriate to its face and anatomy, calm readable pose"),
 ("field-interaction",192,192,"actively investigating a tiny glowing Thread-magic sprout on the ground, curious natural field interaction, both the Guardian and the small sprout clearly visible"),
 ("resting-pose",192,192,"peaceful natural resting or sleeping pose appropriate to its anatomy and species body plan, relaxed content expression, all original body parts coherent"),
)
VARIANT_NAMES=tuple(x[0] for x in VARIANTS)

image=(modal.Image.debian_slim(python_version="3.11").pip_install("accelerate","diffusers","pillow>=10.4,<12","safetensors","sentencepiece","torch>=2.6,<3","transformers").add_local_python_source("modal_worker"))
app=modal.App(APP_NAME); model_cache=modal.Volume.from_name(MODEL_VOLUME,create_if_missing=True)


def _seed(gid:int,index:int)->int:
 return 310_000 + gid*10 + index

def _prompt(pose:str)->str:
 return ("Use the supplied accepted Guardian master as the strict identity reference. Preserve the exact same individual creature: same exterior body plan, exact number and arrangement of legs/wings/tails/ears or other appendages, same face, markings, colors, proportions, silhouette motifs, and living woven textile integument. Ignore the reference background. "
         "This is a living Plushtopia Guardian, not a new species, not a normal animal, and not a retail plush toy. One creature only except for the explicitly requested tiny interaction prop. Clean polished 2D fantasy JRPG game art, simple pure white background, no scenery, no text, no border, no mutation, no extra limbs, no duplicate body parts, no missing required appendages. "+pose)

def _selected_variants(variants_csv:str):
 names=[x.strip() for x in variants_csv.split(",") if x.strip()] if variants_csv else list(VARIANT_NAMES)
 if not names:
  raise ValueError("at least one Guardian variant must be selected")
 if len(names)!=len(set(names)):
  raise ValueError(f"duplicate Guardian variants requested: {names}")
 unknown=[x for x in names if x not in VARIANT_NAMES]
 if unknown:
  raise ValueError(f"unknown Guardian variants requested: {unknown}; allowed={VARIANT_NAMES}")
 wanted=set(names)
 return tuple(spec for spec in VARIANTS if spec[0] in wanted)

@app.cls(gpu="L4",image=image,volumes={CACHE_DIR:model_cache},scaledown_window=10,timeout=1200)
class VariantRunner:
 @modal.enter()
 def load(self):
  import torch
  from diffusers import DiffusionPipeline
  os.environ.setdefault("HF_HOME",CACHE_DIR); os.environ.setdefault("HF_HUB_CACHE",f"{CACHE_DIR}/hub")
  self.torch=torch; self.pipe=DiffusionPipeline.from_pretrained(MODEL_ID,torch_dtype=torch.bfloat16,cache_dir=CACHE_DIR).to("cuda")
 @modal.method()
 def generate(self, reference_b64:str, gid:int, variants_csv:str="")->dict:
  from PIL import Image
  reference=Image.open(io.BytesIO(base64.b64decode(reference_b64))).convert("RGB")
  selected={x[0] for x in _selected_variants(variants_csv)}
  assets=[]
  for index,(name,w,h,pose) in enumerate(VARIANTS):
   if name not in selected:
    continue
   seed=_seed(gid,index); gen=self.torch.Generator(device="cuda").manual_seed(seed); started=time.monotonic()
   rendered=self.pipe(image=[reference],prompt=_prompt(pose),width=512,height=512,guidance_scale=1.0,num_inference_steps=4,generator=gen).images[0]
   out=io.BytesIO(); rendered.save(out,format="PNG"); raw=out.getvalue()
   assets.append({"name":name,"target":[w,h],"seed":seed,"elapsed_seconds":round(time.monotonic()-started,3),"raw_sha256":hashlib.sha256(raw).hexdigest(),"raw_base64":base64.b64encode(raw).decode("ascii")})
  return {"guardian_id":gid,"model":MODEL_ID,"assets":assets}


def _fit_rgba(source,w:int,h:int,margin:float=.06):
 from PIL import Image
 rgba=source.convert("RGBA"); bbox=rgba.getchannel("A").getbbox()
 if bbox is None: raise RuntimeError("no alpha foreground")
 crop=rgba.crop(bbox); crop.thumbnail((max(1,round(w*(1-2*margin))),max(1,round(h*(1-2*margin)))),Image.Resampling.LANCZOS)
 canvas=Image.new("RGBA",(w,h),(0,0,0,0)); canvas.alpha_composite(crop,((w-crop.width)//2,(h-crop.height)//2)); return canvas

def _white_to_alpha(raw:bytes):
 from PIL import Image
 import numpy as np
 im=Image.open(io.BytesIO(raw)).convert("RGBA")
 arr=np.array(im).astype(np.int32); minimum=arr[:,:,:3].min(axis=2)
 alpha=np.clip((245-minimum)*255/20,0,255).astype(np.uint8)
 out=arr.astype(np.uint8); out[:,:,3]=alpha
 return Image.fromarray(out,"RGBA")

def _validate(image):
 rgba=image.convert("RGBA"); a=rgba.getchannel("A"); bbox=a.getbbox(); w,h=rgba.size
 if bbox is None:return {"valid":False,"error":"no foreground"}
 hist=a.histogram(); frac=(w*h-hist[0])/(w*h); edge=[]
 edge+=list(a.crop((0,0,w,1)).getdata()); edge+=list(a.crop((0,h-1,w,h)).getdata()); edge+=list(a.crop((0,0,1,h)).getdata()); edge+=list(a.crop((w-1,0,w,h)).getdata())
 edge_frac=sum(v>0 for v in edge)/len(edge)
 return {"valid":0.015<=frac<=0.90 and edge_frac<=0.02,"width":w,"height":h,"bbox":list(bbox),"foreground_fraction":round(frac,6),"edge_alpha_fraction":round(edge_frac,6),"has_alpha":True}

def _gid(path:Path)->int:return int(path.stem.rsplit("-",1)[1])

def _process(master:Path,variants_csv:str)->dict:
 from PIL import Image
 gid=_gid(master); raw_master=master.read_bytes()
 with Image.open(io.BytesIO(raw_master)) as im:
  im.load()
  if im.size!=(768,768):raise RuntimeError(f"guardian-{gid:03d} master geometry {im.size}")
 ref=Image.open(io.BytesIO(raw_master)).convert("RGB"); ref.thumbnail((512,512),Image.Resampling.LANCZOS); refbuf=io.BytesIO(); ref.save(refbuf,format="PNG")
 remote=VariantRunner().generate.remote(base64.b64encode(refbuf.getvalue()).decode("ascii"),gid,variants_csv)
 extractor=modal.Cls.from_name(EXTRACTOR_APP,EXTRACTOR_CLASS)()
 outdir=OUT_ROOT/f"guardian-{gid:03d}"; outdir.mkdir(parents=True,exist_ok=True); records=[]; gpu_seconds=0.0
 for item in remote["assets"]:
  raw=base64.b64decode(item.pop("raw_base64"),validate=True); gpu_seconds+=float(item["elapsed_seconds"]); name=item["name"]; w,h=item["target"]
  if name=="field-interaction":
   source=_white_to_alpha(raw); extraction="near_white_alpha_preserve_interaction_prop"
  else:
   ext=extractor.extract.remote({"image_base64":base64.b64encode(raw).decode("ascii")}); source=Image.open(io.BytesIO(base64.b64decode(ext["image_base64"],validate=True))).convert("RGBA"); extraction=f"{ext.get('provider')}:{ext.get('model')}"
  final=_fit_rgba(source,w,h,.06); validation=_validate(final)
  if not validation["valid"]:raise RuntimeError(f"guardian-{gid:03d}/{name} validation failed: {validation}")
  path=outdir/f"{name}.png"; final.save(path,format="PNG"); final_raw=path.read_bytes()
  records.append({**item,"logical_id":f"guardian/guardian-{gid:03d}/{name}","path":str(path),"extraction":extraction,"validation":validation,"sha256":hashlib.sha256(final_raw).hexdigest(),"bytes":len(final_raw)})
 return {"guardian_id":f"guardian-{gid:03d}","master_filename":master.name,"accepted":True,"gpu_seconds":round(gpu_seconds,3),"estimated_generation_cost_usd":round(gpu_seconds*GPU_SECOND_COST_USD,6),"assets":records}

@app.local_entrypoint()
def main(master_root:str,max_parallel:int=4,variants:str=""):
 if not 1<=max_parallel<=MAX_PARALLEL_LANES:raise ValueError(f"max_parallel must be 1..{MAX_PARALLEL_LANES}")
 selected=_selected_variants(variants); selected_names=[x[0] for x in selected]; variants_csv=",".join(selected_names)
 roots=[Path(x) for x in master_root.split(":") if x]; masters=sorted({p.resolve() for r in roots for p in r.rglob("guardian-master__guardian-*.png")},key=_gid); ids=[_gid(p) for p in masters]
 if ids!=list(range(1,97)):raise RuntimeError(f"expected exact Guardian IDs 001..096, count={len(ids)}")
 results=[]; failures=[]
 with ThreadPoolExecutor(max_workers=max_parallel) as pool:
  futs={pool.submit(_process,p,variants_csv):p for p in masters}
  for fut in as_completed(futs):
   p=futs[fut]
   try:results.append(fut.result())
   except Exception as exc:failures.append({"source":str(p),"error":f"{type(exc).__name__}: {exc}"})
 results.sort(key=lambda x:x["guardian_id"]); gpu=round(sum(x["gpu_seconds"] for x in results),3); cost=round(sum(x["estimated_generation_cost_usd"] for x in results),6)
 accepted_assets=sum(len(x["assets"]) for x in results)
 report={"schema":"plushbound.guardian_variant_production.v2","expected_guardians":96,"completed_guardians":len(results),"variant_names":selected_names,"variants_per_guardian":len(selected_names),"accepted_asset_count":accepted_assets,"max_parallel_lanes":max_parallel,"max_physical_gpu_concurrency_contract":8,"gpu_seconds":gpu,"estimated_generation_cost_usd":cost,"failures":failures,"guardians":results}
 OUT_ROOT.mkdir(parents=True,exist_ok=True); (OUT_ROOT/"batch-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n"); print(json.dumps({k:v for k,v in report.items() if k!="guardians"},sort_keys=True))
 expected_assets=96*len(selected_names)
 if failures or len(results)!=96 or accepted_assets!=expected_assets:raise RuntimeError(f"Guardian variant production incomplete: guardians={len(results)}/96 assets={accepted_assets}/{expected_assets} failures={len(failures)}")
