"""Self-contained reduced-V1 catalog for Plushbound Creator Full Outfits.

The production constants are embedded so remote Vera/Modal workers do not depend
on an external scope JSON being bundled into the container. The JSON scope file
remains the human-readable mirror and audit record.
"""
from __future__ import annotations
import json

SELECTED_IDS=tuple(range(1,96,2))
CANARY_IDS=(1,49,95)
VARIANTS=('clean','layered','trimmed','structured')
DESIGN_FAMILIES=(
 ('plushtopia_everyday','complete everyday outfits with stitched layers and readable practical silhouettes'),
 ('victorian_tailored','complete Victorian-inspired coordinated outfits with structured tailoring and restrained ornament'),
 ('japanese_layered','complete Japanese-influenced layered outfits with wrap construction, short coats and sash accents'),
 ('chinese_inspired','complete Chinese-influenced coordinated outfits using cross collars, stand collars, panels and subtle knot detailing'),
 ('adventurer_practical','complete field-ready travel outfits with reinforced layers, belts and practical movement'),
 ('artisan_crafter','complete workshop and crafter outfits with aprons, rolled layers and utility details'),
 ('regional_festival','complete celebratory outfits with ribbons, textile motifs and region-friendly variation'),
 ('scholar_court','complete scholar and court outfits with refined formal layering and elegant silhouettes'),
 ('rugged_frontier','complete weathered frontier outfits with sturdy wraps, layered cloth and travel protection'),
 ('cute_plush','complete soft plush-forward outfits with rounded silhouettes, bows and handcrafted details'),
 ('guardian_fanwear','complete outfits with subtle Guardian-inspired motifs without copying unique Guardian bodies'),
 ('neutral_mixmatch','complete gender-flexible coordinated outfits designed for broad Creator compatibility'),
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
                'logical_id':f'creator/full-outfits/{idx:03d}',
                'design_family':name,
                'variant':variant,
                'brief':brief,
                'dimensions':[144,192],
                'layout':'3x4-48px',
                'runtime_role':'character_creator_rgba_overlay',
                'source_art_required':True,
            })
    return {
        'schema':'plushbound.creator_full_outfits_style_catalog.v1',
        'ledger_total':96,
        'v1_target':48,
        'selected_ids':list(SELECTED_IDS),
        'canary_ids':list(CANARY_IDS),
        'styles':styles,
        'catalog_wide_launch_authorized':False,
        'scope_source':'embedded production constants mirrored by creator_full_outfits_v1_scope.json',
    }

def get_style(style_index:int):
    style_index=int(style_index)
    for style in snapshot()['styles']:
        if style['style_index']==style_index:
            return style
    raise ValueError(f'Creator Full Outfit style {style_index:03d} is outside approved reduced V1 scope')

if __name__=='__main__':
    print(json.dumps(snapshot(),indent=2,sort_keys=True))
