"""Deterministic Plushbound Creator Brows compiler."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image
from creator_brows_style_catalog import get_style, snapshot

CELL=48
WIDTH=144
HEIGHT=192
BROW=(72,58,62,255)


def _front(shape:str, weight:str):
    left=[(20,3),(21,2),(22,3)]
    right=[(25,3),(26,2),(27,3)]
    if shape=="straight":
        left=[(20,3),(21,3),(22,3)]; right=[(25,3),(26,3),(27,3)]
    elif shape in {"gentle_angle","tapered"}:
        left=[(20,3),(21,2),(22,2)]; right=[(25,2),(26,2),(27,3)]
    elif shape=="high_arch":
        left=[(20,4),(21,2),(22,3)]; right=[(25,3),(26,2),(27,4)]
    elif shape=="low_arch":
        left=[(20,4),(21,3),(22,4)]; right=[(25,4),(26,3),(27,4)]
    elif shape=="rounded":
        left=[(20,3),(21,2),(22,3),(21,3)]; right=[(25,3),(26,2),(27,3),(26,3)]
    elif shape=="determined":
        left=[(20,2),(21,2),(22,3)]; right=[(25,3),(26,2),(27,2)]
    pts=left+right
    if weight=="fine":
        pts=[p for p in pts if p[0] not in (20,27)]
    elif weight=="defined":
        pts += [(x,y+1) for x,y in pts if y+1<=4 and x not in (20,27)]
    elif weight=="bold":
        pts += [(x,y+1) for x,y in pts if y+1<=4]
    return list(dict.fromkeys(pts))


def _profile(facing:str, shape:str, weight:str):
    if facing=="left":
        xs=[20,21,22]
    else:
        xs=[25,26,27]
    pts=[(xs[0],3),(xs[1],2),(xs[2],3)]
    if shape=="straight":
        pts=[(x,3) for x in xs]
    elif shape in {"gentle_angle","tapered"}:
        pts=[(xs[0],3),(xs[1],2),(xs[2],2)] if facing=="left" else [(xs[0],2),(xs[1],2),(xs[2],3)]
    elif shape=="high_arch":
        pts=[(xs[0],4),(xs[1],2),(xs[2],3)] if facing=="left" else [(xs[0],3),(xs[1],2),(xs[2],4)]
    elif shape=="low_arch":
        pts=[(xs[0],4),(xs[1],3),(xs[2],4)]
    elif shape=="rounded":
        pts += [(xs[1],3)]
    elif shape=="determined":
        pts=[(xs[0],2),(xs[1],2),(xs[2],3)] if facing=="left" else [(xs[0],3),(xs[1],2),(xs[2],2)]
    if weight=="fine":
        pts=pts[1:]
    elif weight=="defined":
        pts += [(x,y+1) for x,y in pts if y+1<=4 and x not in (xs[0],xs[-1])]
    elif weight=="bold":
        pts += [(x,y+1) for x,y in pts if y+1<=4]
    return list(dict.fromkeys(pts))


def _stamp(sheet:Image.Image,col:int,row:int,pts):
    pix=sheet.load(); ox,oy=col*CELL,row*CELL
    for x,y in pts:
        if not (0<=x<CELL and 0<=y<CELL):
            raise RuntimeError("brow motif escaped 48px cell")
        pix[ox+x,oy+y]=BROW


def compile_style(index:int):
    style=get_style(index)
    sheet=Image.new("RGBA",(WIDTH,HEIGHT),(0,0,0,0))
    for col in range(3):
        _stamp(sheet,col,0,_front(style["shape_name"],style["weight_name"]))
        _stamp(sheet,col,1,_profile("left",style["shape_name"],style["weight_name"]))
        _stamp(sheet,col,2,_profile("right",style["shape_name"],style["weight_name"]))
    alpha=sheet.getchannel("A")
    if alpha.getbbox() is None:
        raise RuntimeError("compiled brow overlay is empty")
    if alpha.crop((0,144,144,192)).getbbox() is not None:
        raise RuntimeError("up-facing row must remain transparent")
    for row in (0,1,2):
        ref=sheet.crop((0,row*CELL,CELL,(row+1)*CELL))
        for col in (1,2):
            other=sheet.crop((col*CELL,row*CELL,(col+1)*CELL,(row+1)*CELL))
            if ref.tobytes()!=other.tobytes():
                raise RuntimeError("movement-phase brow drift")
    for row in (0,1,2):
        for col in range(3):
            bbox=alpha.crop((col*CELL,row*CELL,(col+1)*CELL,(row+1)*CELL)).getbbox()
            if bbox is None or bbox[0] < 18 or bbox[2] > 30 or bbox[1] < 1 or bbox[3] > 6:
                raise RuntimeError("brow escaped locked face-safe window")
    report={
        "schema":"plushbound.creator_brows_batch.v1",
        "style_index":index,
        "logical_id":style["logical_id"],
        "style":style,
        "dimensions":[WIDTH,HEIGHT],
        "layout":"3x4-48px",
        "mode":"RGBA",
        "runtime_role":"direct_rgba_overlay",
        "runtime_tintable":True,
        "deterministic":True,
        "paid_render_count":0,
        "paid_extraction_count":0,
        "validation":{"nonempty":True,"up_row_empty":True,"movement_phase_repeat_consistent":True,"face_safe_window_confined":True},
        "requires_locked_body_visual_qc":True,
        "catalog_wide_launch_authorized":False,
    }
    return sheet,report


def main():
    p=argparse.ArgumentParser(); p.add_argument("--style-index",type=int,required=True); p.add_argument("--output-root",default="creator-brows-batch-output")
    args=p.parse_args()
    sheet,report=compile_style(args.style_index)
    root=Path(args.output_root)/f"style-{args.style_index:03d}"; root.mkdir(parents=True,exist_ok=True)
    png=root/f"creator-brows-{args.style_index:03d}.png"; sheet.save(png,optimize=True)
    report["sha256"]=hashlib.sha256(png.read_bytes()).hexdigest()
    (root/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    (root/"catalog_snapshot.json").write_text(json.dumps(snapshot(),indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,sort_keys=True))

if __name__=="__main__":
    main()
