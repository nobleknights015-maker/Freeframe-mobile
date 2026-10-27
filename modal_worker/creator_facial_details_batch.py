"""Deterministic Plushbound Creator Facial Details compiler."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image
from creator_facial_details_style_catalog import get_style, snapshot

CELL=48
WIDTH=144
HEIGHT=192
FRECKLE=(116,77,63,220)
BLUSH=(183,104,110,145)
MARK=(82,56,58,235)
SCAR=(137,87,80,215)
STITCH=(105,74,91,235)


def _front(base:str):
    if base=="nose_freckles": return [(22,7,FRECKLE),(24,7,FRECKLE),(26,7,FRECKLE)]
    if base=="cheek_freckles": return [(19,8,FRECKLE),(20,9,FRECKLE),(21,8,FRECKLE),(27,8,FRECKLE),(28,9,FRECKLE),(29,8,FRECKLE)]
    if base=="beauty_mark_left": return [(20,9,MARK)]
    if base=="beauty_mark_right": return [(28,9,MARK)]
    if base=="soft_blush": return [(19,9,BLUSH),(20,9,BLUSH),(21,9,BLUSH),(27,9,BLUSH),(28,9,BLUSH),(29,9,BLUSH)]
    if base=="under_eye_marks": return [(21,7,MARK),(22,7,MARK),(26,7,MARK),(27,7,MARK)]
    if base=="cheek_stripe_left": return [(19,8,STITCH),(20,9,STITCH),(21,10,STITCH)]
    if base=="cheek_stripe_right": return [(29,8,STITCH),(28,9,STITCH),(27,10,STITCH)]
    if base=="cheek_scar_left": return [(19,7,SCAR),(20,8,SCAR),(21,9,SCAR)]
    if base=="cheek_scar_right": return [(29,7,SCAR),(28,8,SCAR),(27,9,SCAR)]
    if base=="stitch_accent": return [(20,8,STITCH),(21,8,STITCH),(22,8,STITCH),(21,7,STITCH),(21,9,STITCH)]
    if base=="nose_mark": return [(24,7,MARK)]
    raise ValueError(base)


def _profile(facing:str, base:str):
    cx=21 if facing=="left" else 27
    inward=1 if facing=="left" else -1
    if base in {"nose_freckles","nose_mark"}:
        color=FRECKLE if base=="nose_freckles" else MARK
        return [(cx+inward,7,color)]
    if base=="cheek_freckles": return [(cx,8,FRECKLE),(cx,9,FRECKLE)]
    if base in {"beauty_mark_left","beauty_mark_right"}: return [(cx,9,MARK)]
    if base=="soft_blush": return [(cx,9,BLUSH),(cx+inward,9,BLUSH)]
    if base=="under_eye_marks": return [(cx,7,MARK),(cx+inward,7,MARK)]
    if base in {"cheek_stripe_left","cheek_stripe_right"}: return [(cx,8,STITCH),(cx+inward,9,STITCH)]
    if base in {"cheek_scar_left","cheek_scar_right"}: return [(cx,7,SCAR),(cx+inward,8,SCAR),(cx+2*inward,9,SCAR)]
    if base=="stitch_accent": return [(cx,8,STITCH),(cx+inward,8,STITCH),(cx+inward,7,STITCH),(cx+inward,9,STITCH)]
    raise ValueError(base)


def _expand(pts, level:int):
    out=list(pts)
    if level>=2:
        for x,y,c in list(pts):
            if (x+y)%2==0 and y+1<=11: out.append((x,y+1,c))
    if level>=3:
        for x,y,c in list(pts):
            if x+1<=30 and (x*y)%2==0: out.append((x+1,y,c))
    if level>=4:
        for x,y,c in list(pts):
            if x-1>=18 and y+1<=11: out.append((x-1,y+1,c))
    seen=set(); dedup=[]
    for p in out:
        key=(p[0],p[1])
        if key in seen: continue
        seen.add(key); dedup.append(p)
    return dedup


def _stamp(sheet:Image.Image,col:int,row:int,pts):
    pix=sheet.load(); ox,oy=col*CELL,row*CELL
    for x,y,c in pts:
        if not (0<=x<CELL and 0<=y<CELL): raise RuntimeError("facial detail escaped 48px cell")
        pix[ox+x,oy+y]=c


def compile_style(index:int):
    style=get_style(index)
    sheet=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    for col in range(3):
        _stamp(sheet,col,0,_expand(_front(style["base_name"]),style["level"]))
        _stamp(sheet,col,1,_expand(_profile("left",style["base_name"]),style["level"]))
        _stamp(sheet,col,2,_expand(_profile("right",style["base_name"]),style["level"]))
    alpha=sheet.getchannel("A")
    if alpha.getbbox() is None: raise RuntimeError("compiled facial-detail overlay is empty")
    if alpha.crop((0,144,144,192)).getbbox() is not None: raise RuntimeError("up-facing row must remain transparent")
    for row in (0,1,2):
        ref=sheet.crop((0,row*CELL,CELL,(row+1)*CELL))
        for col in (1,2):
            other=sheet.crop((col*CELL,row*CELL,(col+1)*CELL,(row+1)*CELL))
            if ref.tobytes()!=other.tobytes(): raise RuntimeError("movement-phase facial-detail drift")
    for row in (0,1,2):
        for col in range(3):
            bbox=alpha.crop((col*CELL,row*CELL,(col+1)*CELL,(row+1)*CELL)).getbbox()
            if bbox is None or bbox[0] < 17 or bbox[2] > 32 or bbox[1] < 5 or bbox[3] > 13:
                raise RuntimeError("facial detail escaped locked face-safe window")
    report={
        "schema":"plushbound.creator_facial_details_batch.v1",
        "style_index":index,
        "logical_id":style["logical_id"],
        "style":style,
        "dimensions":[WIDTH,HEIGHT],
        "layout":"3x4-48px",
        "mode":"RGBA",
        "runtime_role":"direct_rgba_overlay",
        "deterministic":True,
        "paid_render_count":0,
        "paid_extraction_count":0,
        "validation":{"nonempty":True,"up_row_empty":True,"movement_phase_repeat_consistent":True,"face_safe_window_confined":True},
        "requires_locked_body_visual_qc":True,
        "catalog_wide_launch_authorized":False,
    }
    return sheet,report


def main():
    p=argparse.ArgumentParser(); p.add_argument("--style-index",type=int,required=True); p.add_argument("--output-root",default="creator-facial-details-batch-output")
    args=p.parse_args()
    sheet,report=compile_style(args.style_index)
    root=Path(args.output_root)/f"style-{args.style_index:03d}"; root.mkdir(parents=True,exist_ok=True)
    png=root/f"creator-facial-details-{args.style_index:03d}.png"; sheet.save(png,optimize=True)
    report["sha256"]=hashlib.sha256(png.read_bytes()).hexdigest()
    (root/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    (root/"catalog_snapshot.json").write_text(json.dumps(snapshot(),indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))

if __name__=="__main__":
    main()
