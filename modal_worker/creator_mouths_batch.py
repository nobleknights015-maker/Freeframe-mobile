"""Deterministic Plushbound Creator Mouths compiler."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image
from creator_mouths_style_catalog import get_style, snapshot

CELL=48
WIDTH=144
HEIGHT=192
LINE=(105,68,70,255)
DARK=(79,50,54,255)
LIP=(151,91,96,255)
INNER=(66,42,46,255)


def _base_front(shape:str):
    if shape=="neutral":
        return [(22,9,LINE),(23,9,LINE),(24,9,LINE),(25,9,LINE)]
    if shape=="soft_smile":
        return [(21,8,LINE),(22,9,LINE),(23,10,LINE),(24,10,LINE),(25,9,LINE),(26,8,LINE)]
    if shape=="bright_smile":
        return [(21,8,LINE),(22,9,LINE),(23,10,LINE),(24,10,LINE),(25,9,LINE),(26,8,LINE),(23,9,INNER),(24,9,INNER)]
    if shape=="gentle_frown":
        return [(21,10,LINE),(22,9,LINE),(23,8,LINE),(24,8,LINE),(25,9,LINE),(26,10,LINE)]
    if shape=="determined":
        return [(21,9,DARK),(22,9,DARK),(23,9,DARK),(24,9,DARK),(25,9,DARK),(26,9,DARK)]
    if shape=="open_small":
        return [(22,9,LINE),(23,8,LINE),(24,8,LINE),(25,9,LINE),(23,9,INNER),(24,9,INNER)]
    if shape=="pout":
        return [(22,9,LINE),(23,8,LINE),(24,8,LINE),(25,9,LINE),(23,10,LINE),(24,10,LINE)]
    if shape=="cat_smile":
        return [(21,8,LINE),(22,9,LINE),(23,8,LINE),(24,9,LINE),(25,8,LINE),(26,9,LINE)]
    raise ValueError(shape)


def _base_profile(facing:str, shape:str):
    cx=22 if facing=="left" else 25
    inward=1 if facing=="left" else -1
    if shape=="neutral":
        return [(cx,9,LINE),(cx+inward,9,LINE)]
    if shape in {"soft_smile","bright_smile","cat_smile"}:
        pts=[(cx,8,LINE),(cx+inward,9,LINE)]
        if shape=="bright_smile": pts.append((cx+inward,8,INNER))
        return pts
    if shape=="gentle_frown":
        return [(cx,10,LINE),(cx+inward,9,LINE)]
    if shape=="determined":
        return [(cx,9,DARK),(cx+inward,9,DARK)]
    if shape=="open_small":
        return [(cx,8,LINE),(cx,9,INNER),(cx+inward,9,LINE)]
    if shape=="pout":
        return [(cx,8,LINE),(cx,9,LINE),(cx+inward,10,LINE)]
    raise ValueError(shape)


def _apply_weight(pts, weight:str):
    out=list(pts)
    if weight=="fine":
        return out[::2] if len(out)>2 else out
    if weight=="natural":
        return out
    if weight=="defined":
        for x,y,c in list(pts):
            if y+1 <= 11 and c != INNER:
                out.append((x,y+1,DARK if c==DARK else LINE))
    elif weight=="soft_lip":
        recol=[]
        for x,y,c in out:
            recol.append((x,y,LIP if c != INNER else INNER))
        out=recol
        for x,y,c in list(out):
            if y+1 <= 11 and c != INNER and x in (23,24):
                out.append((x,y+1,LIP))
    else:
        raise ValueError(weight)
    seen=set(); dedup=[]
    for p in out:
        key=(p[0],p[1])
        if key in seen: continue
        seen.add(key); dedup.append(p)
    return dedup


def _stamp(sheet:Image.Image,col:int,row:int,pts):
    pix=sheet.load(); ox,oy=col*CELL,row*CELL
    for x,y,c in pts:
        if not (0<=x<CELL and 0<=y<CELL):
            raise RuntimeError("mouth motif escaped 48px cell")
        pix[ox+x,oy+y]=c


def compile_style(index:int):
    style=get_style(index)
    sheet=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    for col in range(3):
        _stamp(sheet,col,0,_apply_weight(_base_front(style["shape_name"]),style["weight_name"]))
        _stamp(sheet,col,1,_apply_weight(_base_profile("left",style["shape_name"]),style["weight_name"]))
        _stamp(sheet,col,2,_apply_weight(_base_profile("right",style["shape_name"]),style["weight_name"]))
    alpha=sheet.getchannel("A")
    if alpha.getbbox() is None:
        raise RuntimeError("compiled mouth overlay is empty")
    if alpha.crop((0,144,144,192)).getbbox() is not None:
        raise RuntimeError("up-facing row must remain transparent")
    for row in (0,1,2):
        ref=sheet.crop((0,row*CELL,CELL,(row+1)*CELL))
        for col in (1,2):
            other=sheet.crop((col*CELL,row*CELL,(col+1)*CELL,(row+1)*CELL))
            if ref.tobytes()!=other.tobytes():
                raise RuntimeError("movement-phase mouth drift")
    for row in (0,1,2):
        for col in range(3):
            bbox=alpha.crop((col*CELL,row*CELL,(col+1)*CELL,(row+1)*CELL)).getbbox()
            if bbox is None or bbox[0] < 19 or bbox[2] > 29 or bbox[1] < 6 or bbox[3] > 13:
                raise RuntimeError("mouth escaped locked face-safe window")
    report={
        "schema":"plushbound.creator_mouths_batch.v1",
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
    p=argparse.ArgumentParser(); p.add_argument("--style-index",type=int,required=True); p.add_argument("--output-root",default="creator-mouths-batch-output")
    args=p.parse_args()
    sheet,report=compile_style(args.style_index)
    root=Path(args.output_root)/f"style-{args.style_index:03d}"; root.mkdir(parents=True,exist_ok=True)
    png=root/f"creator-mouths-{args.style_index:03d}.png"; sheet.save(png,optimize=True)
    report["sha256"]=hashlib.sha256(png.read_bytes()).hexdigest()
    (root/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    (root/"catalog_snapshot.json").write_text(json.dumps(snapshot(),indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))

if __name__=="__main__":
    main()
