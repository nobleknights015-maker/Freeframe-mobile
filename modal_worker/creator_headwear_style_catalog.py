"""Self-contained reduced-V1 catalog for Plushbound Creator Headwear."""
from __future__ import annotations
import json

SELECTED_IDS=tuple(range(1,64,2))
CANARY_IDS=(1,33,63)
VARIANTS=('clean','layered','trimmed','structured')
DESIGN_FAMILIES=(
 ('plushtopia_everyday','everyday caps, soft hats and practical headpieces with visible stitching and fabric structure'),
 ('victorian_tailored','Victorian-inspired hats and small formal headpieces with restrained ribbons and trim'),
 ('japanese_layered','Japanese-influenced cloth headwear, wraps and travel hats adapted to the Plushbound world'),
 ('chinese_inspired','Chinese-influenced soft caps and formal textile headpieces with subtle knot and panel motifs'),
 ('adventurer_practical','field-ready hoods, caps and protective travel headwear with clean sprite silhouettes'),
 ('artisan_crafter','workshop headwear, kerchiefs and crafter caps with handcrafted utility details'),
 ('regional_festival','celebratory headwear with ribbons, textile motifs and regional variation'),
 ('cute_plush','soft plush-forward hats and headpieces with rounded silhouettes, ears or bows used sparingly'),
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
                'logical_id':f'creator/headwear/{idx:03d}',
                'design_family':name,
                'variant':variant,
                'brief':brief,
                'dimensions':[144,192],
                'layout':'3x4-48px',
                'runtime_role':'character_creator_rgba_overlay',
                'source_art_required':True,
            })
    return {
        'schema':'plushbound.creator_headwear_style_catalog.v1',
        'ledger_total':64,
        'v1_target':32,
        'selected_ids':list(SELECTED_IDS),
        'canary_ids':list(CANARY_IDS),
        'styles':styles,
        'catalog_wide_launch_authorized':False,
        'scope_source':'embedded production constants mirrored by creator_headwear_v1_scope.json',
    }

def get_style(style_index:int):
    style_index=int(style_index)
    for style in snapshot()['styles']:
        if style['style_index']==style_index:
            return style
    raise ValueError(f'Creator Headwear style {style_index:03d} is outside approved reduced V1 scope')

if __name__=='__main__':
    print(json.dumps(snapshot(),indent=2,sort_keys=True))
