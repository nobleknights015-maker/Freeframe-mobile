"""Guardian deterministic runtime production: 96 accepted masters -> 480 safe derivatives.

This path uses semantic extraction and deterministic packaging only. It never diffusion-
generates pose/expression variants; those remain a separate gated production family.
"""
from __future__ import annotations

import base64
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import modal
from PIL import Image

APP_NAME = "freeframe-guardian-runtime-production"
EXTRACTOR_APP = "freeframe-worker"
EXTRACTOR_CLASS = "FreeFrameExtractor"
OUT_ROOT = Path("guardian-runtime-production")
TARGETS = {
    "overworld": (144, 192, 0.10),
    "portrait": (288, 288, 0.04),
    "silhouette": (192, 192, 0.08),
    "battle-idle": (192, 192, 0.08),
    "icon": (96, 96, 0.06),
}
DEFERRED = ["battle-action", "battle-hurt", "bond-expression", "field-interaction", "resting-pose"]
app = modal.App(APP_NAME)


def _fit(subject: Image.Image, w: int, h: int, margin: float) -> Image.Image:
    rgba=subject.convert("RGBA"); bbox=rgba.getchannel("A").getbbox()
    if bbox is None: raise RuntimeError("semantic extraction produced no foreground")
    crop=rgba.crop(bbox); iw=max(1,round(w*(1-2*margin))); ih=max(1,round(h*(1-2*margin)))
    crop.thumbnail((iw,ih),Image.Resampling.LANCZOS)
    canvas=Image.new("RGBA",(w,h),(0,0,0,0)); canvas.alpha_composite(crop,((w-crop.width)//2,(h-crop.height)//2)); return canvas


def _silhouette(subject: Image.Image,w:int,h:int,margin:float)->Image.Image:
    fitted=_fit(subject,w,h,margin); alpha=fitted.getchannel("A"); out=Image.new("RGBA",fitted.size,(18,18,22,0)); out.putalpha(alpha); return out


def _valid(image:Image.Image)->dict:
    rgba=image.convert("RGBA"); a=rgba.getchannel("A"); bbox=a.getbbox(); w,h=rgba.size
    if bbox is None:return {"valid":False,"error":"no foreground"}
    hist=a.histogram(); frac=(w*h-hist[0])/(w*h); edge=[]
    edge += list(a.crop((0,0,w,1)).getdata()); edge += list(a.crop((0,h-1,w,h)).getdata())
    edge += list(a.crop((0,0,1,h)).getdata()); edge += list(a.crop((w-1,0,w,h)).getdata())
    edge_frac=sum(v>0 for v in edge)/len(edge)
    return {"valid":0.02<=frac<=0.88 and edge_frac<=0.02,"width":w,"height":h,"foreground_fraction":round(frac,6),"edge_alpha_fraction":round(edge_frac,6),"bbox":list(bbox),"has_alpha":True}


def _id_from_path(path:Path)->int:
    stem=path.stem
    return int(stem.rsplit("-",1)[1])


def _process(path:Path)->dict:
    gid=_id_from_path(path); raw=path.read_bytes()
    with Image.open(io.BytesIO(raw)) as src:
        src.load()
        if src.size!=(768,768): raise RuntimeError(f"guardian-{gid:03d}: source geometry {src.size}")
    extractor=modal.Cls.from_name(EXTRACTOR_APP,EXTRACTOR_CLASS)()
    response=extractor.extract.remote({"image_base64":base64.b64encode(raw).decode("ascii")})
    extracted=base64.b64decode(response["image_base64"],validate=True); subject=Image.open(io.BytesIO(extracted)).convert("RGBA")
    out_dir=OUT_ROOT/f"guardian-{gid:03d}"; out_dir.mkdir(parents=True,exist_ok=True)
    records={}
    for name,(w,h,margin) in TARGETS.items():
        image=_silhouette(subject,w,h,margin) if name=="silhouette" else _fit(subject,w,h,margin)
        v=_valid(image)
        if not v["valid"]: raise RuntimeError(f"guardian-{gid:03d}/{name}: {v}")
        path_out=out_dir/f"{name}.png"; image.save(path_out,format="PNG")
        records[name]={"logical_id":f"guardian/guardian-{gid:03d}/{name}","path":str(path_out),"validation":v}
    return {"guardian_id":f"guardian-{gid:03d}","source":str(path),"extractor_provider":response.get("provider"),"extractor_model":response.get("model"),"derived":records,"deferred":DEFERRED}


@app.local_entrypoint()
def main(master_root: str, max_parallel: int = 6):
    if not 1<=max_parallel<=10: raise ValueError("max_parallel must be 1..10")
    roots=[Path(x) for x in master_root.split(":") if x]
    masters=sorted({p.resolve() for root in roots for p in root.rglob("guardian-master__guardian-*.png")}, key=_id_from_path)
    ids=[_id_from_path(p) for p in masters]
    if ids != list(range(1,97)): raise RuntimeError(f"expected exact Guardian IDs 001..096, got {ids[:5]}...{ids[-5:]} count={len(ids)}")
    results=[]; failures=[]
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures={pool.submit(_process,p):p for p in masters}
        for future in as_completed(futures):
            p=futures[future]
            try: results.append(future.result())
            except Exception as exc: failures.append({"source":str(p),"error":str(exc)})
    results.sort(key=lambda x:x["guardian_id"])
    report={"schema":"plushbound.guardian_runtime_production.v1","expected_guardians":96,"completed_guardians":len(results),"derived_per_guardian":5,"derived_total":len(results)*5,"deferred_per_guardian":5,"deferred_total":96*5,"max_parallel":max_parallel,"diffusion_generation_count":0,"failures":failures,"guardians":results}
    OUT_ROOT.mkdir(parents=True,exist_ok=True); (OUT_ROOT/"batch-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="guardians"},sort_keys=True))
    if failures or len(results)!=96: raise RuntimeError(f"Guardian deterministic production incomplete: completed={len(results)} failures={len(failures)}")
