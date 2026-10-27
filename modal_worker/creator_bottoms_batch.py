"""Bounded source-art + deterministic compiler for reduced-V1 Creator Bottoms."""
from __future__ import annotations
import base64, io, json, os, time
from pathlib import Path
import modal
from PIL import Image, ImageChops, ImageEnhance, ImageFilter
from modal_worker.creator_bottoms_style_catalog import get_style, snapshot

APP_NAME="freeframe-creator-bottoms-batch"
MODEL_ID="black-forest-labs/FLUX.2-klein-4B"
CACHE_DIR="/cache"
MODEL_VOLUME="freeframe-model-cache"
OUT_ROOT="creator-bottoms-batch-output"
CELL=48; SHEET_W=144; SHEET_H=192
DIRECTIONS=("down","left","right","up")
DIRECTION_TEXT={"down":"front-facing view toward the viewer","left":"left profile view","right":"right profile view","up":"rear-facing view showing the back of the garment"}
MASK_PNG_B64="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"

image=(modal.Image.debian_slim(python_version="3.11")
       .apt_install("libgl1","libglib2.0-0")
       .pip_install("accelerate","diffusers","numpy","pillow>=10.4,<12","safetensors","sentencepiece","torch>=2.6,<3","transformers")
       .add_local_python_source("modal_worker"))
app=modal.App(APP_NAME)
model_cache=modal.Volume.from_name(MODEL_VOLUME,create_if_missing=True)

def _style_prompt(style):
    return (
      "isolated original Plushtopia fantasy JRPG lower-body garment only, "
      f"{style['brief']}, {style['variant']} interpretation, "
      "RPG Maker MV cover-art / MV Trinity-inspired polish without copying proprietary artwork, "
      "clean anime-JRPG fabric rendering, visible stitching and handcrafted textile detail, restrained neutral base colors suitable for later tinting, "
      "lower garment only on pure white background: no person, no mannequin, no torso, no head, no face, no skin, no hands, no shirt, no shoes, no accessories, no text, one centered object"
    )

def _direction_prompt(style,direction):
    return (
      "Preserve the exact same lower garment identity, construction, seams, trim, fabric, and color from the reference. "
      f"Render the isolated lower-body garment only as a {DIRECTION_TEXT[direction]}. "
      f"Design brief: {style['brief']}; variant: {style['variant']}. "
      "No person, mannequin, torso, head, skin, hands, shirt, shoes, or accessories. "
      "Keep waistband, hem, folds, panels and leg separation readable at small JRPG sprite scale, centered on pure white background, no text, no border."
    )

@app.cls(gpu="L4",image=image,volumes={CACHE_DIR:model_cache},scaledown_window=120,timeout=1200)
class CreatorBottomsBatchRunner:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import DiffusionPipeline
        os.environ.setdefault("HF_HOME",CACHE_DIR); os.environ.setdefault("HF_HUB_CACHE",f"{CACHE_DIR}/hub")
        self.torch=torch
        self.pipe=DiffusionPipeline.from_pretrained(MODEL_ID,torch_dtype=torch.bfloat16,cache_dir=CACHE_DIR).to("cuda")
    def _generate(self,prompt,seed,reference=None):
        gen=self.torch.Generator(device="cuda").manual_seed(seed)
        kw=dict(prompt=prompt,width=512,height=512,guidance_scale=1.0,num_inference_steps=4,generator=gen)
        if reference is not None: kw["image"]=[reference]
        started=time.monotonic(); out=self.pipe(**kw).images[0]
        return out,round(time.monotonic()-started,3)
    @modal.method()
    def generate(self,style_index:int):
        style=get_style(style_index); seed0=950000+int(style_index)*100
        reference,ref_seconds=self._generate(_style_prompt(style),seed0)
        rb=io.BytesIO(); reference.save(rb,format="PNG")
        dirs=[]
        for offset,direction in enumerate(DIRECTIONS,start=1):
            frame,elapsed=self._generate(_direction_prompt(style,direction),seed0+offset,reference)
            fb=io.BytesIO(); frame.save(fb,format="PNG")
            dirs.append({"direction":direction,"seed":seed0+offset,"seconds":elapsed,"png":base64.b64encode(fb.getvalue()).decode("ascii")})
        return {"style":style,"model":MODEL_ID,"reference_seed":seed0,"reference_seconds":ref_seconds,"reference_png":base64.b64encode(rb.getvalue()).decode("ascii"),"directions":dirs}

def _extract(encoded):
    extractor=modal.Cls.from_name("freeframe-worker","FreeFrameExtractor")()
    result=extractor.extract.remote({"image_base64":encoded})
    raw=base64.b64decode(result["image_base64"],validate=True)
    with Image.open(io.BytesIO(raw)) as im:
        rgba=im.convert("RGBA"); bbox=rgba.getchannel("A").getbbox()
        if bbox is None: raise RuntimeError("bottom extraction is empty")
        return rgba.crop(bbox)

def _locked_mask():
    with Image.open(io.BytesIO(base64.b64decode(MASK_PNG_B64))) as im: mask=im.convert("L")
    if mask.size!=(SHEET_W,SHEET_H): raise RuntimeError("locked bottom mask has wrong dimensions")
    return mask

def _style_mask(base,style):
    family=style["design_family"]; variant=style["variant"]; m=base.copy()
    if family in {"everyday_skirts","japanese_layered","regional_festival","cute_plush"} or variant=="layered":
        m=m.filter(ImageFilter.MaxFilter(3))
    elif family in {"victorian_tailored","adventurer_utility"} or variant=="structured":
        m=m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    return m

def _compile_sheet(style,pieces):
    base=_style_mask(_locked_mask(),style)
    out=Image.new("RGBA",(SHEET_W,SHEET_H),(0,0,0,0)); stats=[]
    for row,direction in enumerate(DIRECTIONS):
        piece=pieces[direction]
        for col in range(3):
            box=(col*CELL,row*CELL,(col+1)*CELL,(row+1)*CELL)
            cell_mask=base.crop(box); bbox=cell_mask.getbbox()
            if bbox is None: raise RuntimeError(f"empty bottom mask row={row} col={col}")
            x0,y0,x1,y1=bbox
            if y0<17 or y1>46: raise RuntimeError("bottom mask escaped lower-body safe window")
            tex=piece.resize((x1-x0,y1-y0),Image.Resampling.LANCZOS)
            patch=Image.new("RGBA",(CELL,CELL),(0,0,0,0)); patch.paste(tex,(x0,y0)); patch.putalpha(cell_mask)
            eroded=cell_mask.filter(ImageFilter.MinFilter(3)); edge=ImageChops.subtract(cell_mask,eroded)
            dark=ImageEnhance.Brightness(patch).enhance(0.66); patch=Image.composite(dark,patch,edge)
            out.alpha_composite(patch,dest=(col*CELL,row*CELL))
            stats.append({"direction":direction,"phase":col,"bbox":[x0,y0,x1,y1]})
    return out,{"locked_motion_mask":True,"cells":stats}

@app.local_entrypoint()
def main(style_index:int):
    style_index=int(style_index); style=get_style(style_index)
    out_dir=Path(OUT_ROOT)/f"style-{style_index:03d}"; src=out_dir/"sources"; src.mkdir(parents=True,exist_ok=True)
    remote=CreatorBottomsBatchRunner().generate.remote(style_index)
    (out_dir/f"creator-bottom-{style_index:03d}-reference.png").write_bytes(base64.b64decode(remote["reference_png"],validate=True))
    pieces={}; extraction=[]
    for item in remote["directions"]:
        piece=_extract(item["png"]); pieces[item["direction"]]=piece
        piece.save(src/f"{item['direction']}-extracted.png",format="PNG",optimize=False)
        extraction.append({"direction":item["direction"],"seed":item["seed"],"seconds":item["seconds"],"extracted_size":list(piece.size)})
    sheet,geometry=_compile_sheet(style,pieces)
    p=out_dir/f"creator-bottom-{style_index:03d}.png"; sheet.save(p,format="PNG",optimize=False)
    if sheet.getchannel("A").getbbox() is None: raise RuntimeError("compiled bottom sheet is empty")
    report={
      "schema":"plushbound.creator_bottoms_batch.v1","style_index":style_index,"logical_id":style["logical_id"],"style":style,
      "status":"generated_pending_visual_review","model":remote["model"],"paid_render_count":5,"paid_extraction_count":4,
      "reference_seed":remote["reference_seed"],"reference_seconds":remote["reference_seconds"],"extraction_backend":"deployed_birefnet",
      "extraction":extraction,"dimensions":[SHEET_W,SHEET_H],"layout":"3x4-48px","geometry":geometry,
      "compiler_owns_final_geometry":True,"generated_alpha_discarded":True,"catalog_wide_launch_authorized":False,
      "next_gate":"locked-body visual QC before banking"}
    (out_dir/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    (out_dir/"catalog_snapshot.json").write_text(json.dumps(snapshot(),indent=2,sort_keys=True)+"\n")
    print(json.dumps({"schema":report["schema"],"style_index":style_index,"renders":5,"extractions":4},sort_keys=True))
