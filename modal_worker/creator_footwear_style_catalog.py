"""Self-contained reduced-V1 catalog for Plushbound Creator Footwear."""
from __future__ import annotations
import json

SELECTED_IDS=tuple(range(1,64,2))
CANARY_IDS=(1,33,63)
VARIANTS=('clean','layered','trimmed','rugged')
DESIGN_FAMILIES=(
 ('plushtopia_everyday','comfortable everyday shoes and boots with stitched fabric or soft leather details'),
 ('victorian_tailored','refined Victorian-inspired boots, button shoes and formal footwear with restrained trim'),
 ('japanese_layered','Japanese-influenced sandals, tabi-like boots and layered travel footwear adapted to Plushtopia'),
 ('chinese_inspired','Chinese-influenced cloth shoes and short boots with subtle knot, panel and embroidered accents'),
 ('adventurer_practical','field-ready travel boots and reinforced shoes built for readable JRPG movement'),
 ('artisan_workwear','durable workshop shoes and practical crafter boots with handcrafted construction'),
 ('regional_festival','celebratory footwear with ribbons, textile motifs and region-friendly variation'),
 ('cute_plush','soft plush-forward shoes and boots with rounded silhouettes and whimsical stitch details'),
)
assert len(SELECTED_IDS)==32==len(set(SELECTED_IDS))
assert set(CANARY_IDS).issubset(SELECTED_IDS)
assert len(DESIGN_FAMILIES)==8

def snapshot():
    styles=[]
    for fi,(name,brief) in enumerate(DESIGN_FAMILIES):
        for vi,variant in enumerate(VARIANTS):
            idx=SELECTED_IDS[fi*4+vi]
            styles.append({
                'style_index':idx,
                'logical_id':f'creator/footwear/{idx:03d}',
                'design_family':name,
                'variant':variant,
                'brief':brief,
                'dimensions':[144,192],
                'layout':'3x4-48px',
                'runtime_role':'character_creator_rgba_overlay',
                'source_art_required':True,
            })
    return {
        'schema':'plushbound.creator_footwear_style_catalog.v1',
        'ledger_total':64,
        'v1_target':32,
        'selected_ids':list(SELECTED_IDS),
        'canary_ids':list(CANARY_IDS),
        'styles':styles,
        'catalog_wide_launch_authorized':False,
        'scope_source':'embedded production constants mirrored by creator_footwear_v1_scope.json',
    }

def get_style(style_index:int):
    style_index=int(style_index)
    for style in snapshot()['styles']:
        if style['style_index']==style_index:
            return style
    raise ValueError(f'Creator Footwear style {style_index:03d} is outside approved reduced V1 scope')

if __name__=='__main__':
    print(json.dumps(snapshot(),indent=2,sort_keys=True))
