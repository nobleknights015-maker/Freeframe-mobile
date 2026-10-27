"""Self-contained reduced-V1 catalog for Plushbound Creator Bottoms."""
from __future__ import annotations
import json

SELECTED_IDS=tuple(range(1,96,2))
CANARY_IDS=(1,49,95)
VARIANTS=('clean','layered','trimmed','structured')
DESIGN_FAMILIES=(
 ('everyday_trousers','clean stitched everyday trousers with readable hems and pockets'),
 ('everyday_skirts','simple layered skirts and practical skirt silhouettes with handcrafted trim'),
 ('shorts_cropped','shorts and cropped lower garments designed for travel and casual wear'),
 ('victorian_tailored','tailored Victorian-inspired trousers, split skirts and fitted lower silhouettes'),
 ('japanese_layered','hakama-inspired, wrap-skirt and layered Japanese-influenced lower garments'),
 ('chinese_inspired','flowing trousers and panelled lower garments with restrained Chinese-inspired detailing'),
 ('adventurer_utility','field trousers, reinforced knees, utility straps and travel-ready lower wear'),
 ('artisan_workwear','work trousers, apron-skirt layers and sturdy crafter-focused silhouettes'),
 ('regional_festival','celebratory lower garments with ribbon, trim and textile motifs'),
 ('rugged_frontier','weathered field trousers, wrapped leggings and frontier-ready lower wear'),
 ('cute_plush','soft rounded skirts, bloomers and playful stitched lower silhouettes'),
 ('neutral_mixmatch','gender-flexible lower garments designed to combine cleanly with many tops and outerwear'),
)
assert len(SELECTED_IDS)==48==len(set(SELECTED_IDS))
assert set(CANARY_IDS).issubset(SELECTED_IDS)
assert len(DESIGN_FAMILIES)==12

def snapshot():
    styles=[]
    for fi,(name,brief) in enumerate(DESIGN_FAMILIES):
        for vi,variant in enumerate(VARIANTS):
            idx=SELECTED_IDS[fi*4+vi]
            styles.append({'style_index':idx,'logical_id':f'creator/bottoms/{idx:03d}','design_family':name,'variant':variant,'brief':brief,'dimensions':[144,192],'layout':'3x4-48px','source_art_required':True})
    return {'schema':'plushbound.creator_bottoms_style_catalog.v1','ledger_total':96,'v1_target':48,'selected_ids':list(SELECTED_IDS),'canary_ids':list(CANARY_IDS),'styles':styles,'catalog_wide_launch_authorized':False,'scope_source':'embedded production constants mirrored by creator_bottoms_v1_scope.json'}

def get_style(style_index:int):
    style_index=int(style_index)
    for s in snapshot()['styles']:
        if s['style_index']==style_index:return s
    raise ValueError(f'Creator Bottoms style {style_index:03d} is outside approved reduced V1 scope')

if __name__=='__main__':print(json.dumps(snapshot(),indent=2,sort_keys=True))
