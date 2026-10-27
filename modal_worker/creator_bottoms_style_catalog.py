"""Reduced-V1 deterministic catalog for Plushbound Creator Bottoms."""
from __future__ import annotations
import json
from pathlib import Path
_SCOPE=Path(__file__).with_name('creator_bottoms_v1_scope.json')
_VARIANTS=('clean','layered','trimmed','structured')

def _load():
    d=json.loads(_SCOPE.read_text())
    assert d['schema']=='plushbound.creator_bottoms_v1_scope.v1'
    ids=[int(x) for x in d['selected_ids']]
    assert len(ids)==48==len(set(ids)) and all(1<=x<=96 for x in ids)
    assert len(d['design_families'])==12 and all(int(f['count'])==4 for f in d['design_families'])
    return d

def snapshot():
    d=_load(); styles=[]
    for fi,f in enumerate(d['design_families']):
        for vi in range(4):
            slot=fi*4+vi; idx=int(d['selected_ids'][slot])
            styles.append({'style_index':idx,'logical_id':f'creator/bottoms/{idx:03d}','design_family':f['name'],'variant':_VARIANTS[vi],'brief':f['brief'],'dimensions':[144,192],'layout':'3x4-48px','source_art_required':True})
    return {'schema':'plushbound.creator_bottoms_style_catalog.v1','ledger_total':96,'v1_target':48,'selected_ids':d['selected_ids'],'canary_ids':d['canary_ids'],'styles':styles,'catalog_wide_launch_authorized':False}

def get_style(style_index:int):
    style_index=int(style_index)
    for s in snapshot()['styles']:
        if s['style_index']==style_index:return s
    raise ValueError(f'Creator Bottoms style {style_index:03d} is outside approved reduced V1 scope')

if __name__=='__main__':print(json.dumps(snapshot(),indent=2,sort_keys=True))
