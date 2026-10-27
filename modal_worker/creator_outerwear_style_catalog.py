"""Self-contained reduced-V1 catalog for Plushbound Creator Outerwear."""
from __future__ import annotations
import json

SELECTED_IDS=tuple(range(1,72,2))
CANARY_IDS=(1,37,71)
VARIANTS=('clean','layered','structured')
DESIGN_FAMILIES=(
 ('everyday_jackets','practical stitched jackets and light coats for everyday Plushtopia wear'),
 ('victorian_coats','tailored Victorian-inspired coats and long structured outer layers'),
 ('japanese_haori','haori-inspired and short layered Japanese-influenced outerwear'),
 ('chinese_overrobes','panelled Chinese-influenced overrobes and restrained stand-collar outer layers'),
 ('adventurer_cloaks','travel cloaks, field coats and weather-ready adventurer outerwear'),
 ('artisan_workcoats','work coats and protective crafter layers with visible stitching and utility detail'),
 ('regional_festival','decorative regional festival outer layers with ribbons and textile motifs'),
 ('scholar_court','refined scholar and court outerwear with elegant layered silhouettes'),
 ('rugged_frontier','weathered frontier coats, poncho-like layers and rugged travel protection'),
 ('cute_plush','soft rounded plush-forward capes and coats with handcrafted charm'),
 ('guardian_fanwear','outerwear with subtle Guardian-inspired motifs without copying Guardian bodies'),
 ('neutral_mixmatch','gender-flexible outer layers designed to combine cleanly with many tops and outfits'),
)
assert len(SELECTED_IDS)==36==len(set(SELECTED_IDS))
assert set(CANARY_IDS).issubset(SELECTED_IDS)
assert len(DESIGN_FAMILIES)==12

def snapshot():
    styles=[]
    for fi,(name,brief) in enumerate(DESIGN_FAMILIES):
        for vi,variant in enumerate(VARIANTS):
            idx=SELECTED_IDS[fi*3+vi]
            styles.append({'style_index':idx,'logical_id':f'creator/outerwear/{idx:03d}','design_family':name,'variant':variant,'brief':brief,'dimensions':[144,192],'layout':'3x4-48px','runtime_role':'character_creator_rgba_overlay','source_art_required':True})
    return {'schema':'plushbound.creator_outerwear_style_catalog.v1','ledger_total':72,'v1_target':36,'selected_ids':list(SELECTED_IDS),'canary_ids':list(CANARY_IDS),'styles':styles,'catalog_wide_launch_authorized':False,'scope_source':'embedded production constants mirrored by creator_outerwear_v1_scope.json'}

def get_style(style_index:int):
    style_index=int(style_index)
    for s in snapshot()['styles']:
        if s['style_index']==style_index:return s
    raise ValueError(f'Creator Outerwear style {style_index:03d} is outside approved reduced V1 scope')

if __name__=='__main__':print(json.dumps(snapshot(),indent=2,sort_keys=True))
