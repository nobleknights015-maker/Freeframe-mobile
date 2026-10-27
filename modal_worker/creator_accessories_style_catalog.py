"""Self-contained reduced-V1 catalog for Plushbound Creator Accessories."""
from __future__ import annotations
import json

SELECTED_IDS=tuple(range(1,96,2))
CANARY_IDS=(1,49,95)
VARIANTS=('clean','layered','trimmed','structured')
DESIGN_FAMILIES=(
 ('scarves_neckwear','scarves, kerchiefs and soft neckwear with stitched textile readability'),
 ('belts_sashes','belts, sashes and waist ties with handcrafted clasps and knots'),
 ('bags_pouches','small bags, satchels and pouches suitable for JRPG field silhouettes'),
 ('shoulder_capes','short shoulder capes, capelets and mantle-like accessories'),
 ('gloves_wrist','gloves, cuffs, wrist wraps and textile hand-adjacent accessories without skin'),
 ('charms_brooches','fabric charms, brooches and stitched insignia accents'),
 ('japanese_accents','Japanese-influenced obi ornaments, cords and layered textile accents'),
 ('chinese_accents','Chinese-influenced knots, tassels and decorative fastening accents'),
 ('victorian_accents','Victorian-inspired ribbons, cravats, brooches and tailored accessory pieces'),
 ('regional_festival','festival ribbons, rosettes and region-friendly celebratory accents'),
 ('guardian_motifs','subtle Guardian-inspired charms without copying unique Guardian bodies'),
 ('neutral_mixmatch','gender-flexible utility and decorative accessories for broad Creator compatibility'),
)
assert len(SELECTED_IDS)==48==len(set(SELECTED_IDS))
assert set(CANARY_IDS).issubset(SELECTED_IDS)
assert len(DESIGN_FAMILIES)==12

def snapshot():
    styles=[]
    for fi,(name,brief) in enumerate(DESIGN_FAMILIES):
        for vi,variant in enumerate(VARIANTS):
            idx=SELECTED_IDS[fi*4+vi]
            styles.append({
                'style_index':idx,
                'logical_id':f'creator/accessories/{idx:03d}',
                'design_family':name,
                'variant':variant,
                'brief':brief,
                'dimensions':[144,192],
                'layout':'3x4-48px',
                'runtime_role':'character_creator_rgba_overlay',
                'source_art_required':True,
            })
    return {
        'schema':'plushbound.creator_accessories_style_catalog.v1',
        'ledger_total':96,
        'v1_target':48,
        'selected_ids':list(SELECTED_IDS),
        'canary_ids':list(CANARY_IDS),
        'styles':styles,
        'catalog_wide_launch_authorized':False,
        'scope_source':'embedded production constants mirrored by creator_accessories_v1_scope.json',
    }

def get_style(style_index:int):
    style_index=int(style_index)
    for style in snapshot()['styles']:
        if style['style_index']==style_index:
            return style
    raise ValueError(f'Creator Accessory style {style_index:03d} is outside approved reduced V1 scope')

if __name__=='__main__':
    print(json.dumps(snapshot(),indent=2,sort_keys=True))
