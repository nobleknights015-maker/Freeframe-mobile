"""Deterministic zero-cost tint palette support for Plushbound Creator."""
from __future__ import annotations
import json

NAMES=(
 'plushtopia_neutrals','warm_thread','cool_thread','forest_grove','tide_coast','ember_festival',
 'gale_sky','victorian_muted','japanese_indigo','chinese_lacquer','pastel_plush','earthwork',
 'royal_court','scholar_ink','frontier_dust','artisan_dye','spring_festival','summer_bright',
 'autumn_cloth','winter_soft','guardian_ember','guardian_grove','guardian_tide','guardian_gale',
)
SWATCHES=(
 ('#D9D2C3','#8D7D6B','#4B433B'),('#D8A17A','#A45F45','#6E382D'),('#A9BDD0','#678AA8','#3F5F78'),
 ('#A7B58B','#6F8557','#41543A'),('#A8CAD0','#5E9BA7','#376C78'),('#E3AA7B','#C66A43','#7D3F32'),
 ('#C5D9E8','#83AFC8','#527E99'),('#B8ADA8','#85756F','#574A47'),('#A7B2C7','#536B94','#34445F'),
 ('#D1A08C','#A44E46','#6C3030'),('#D7C4D7','#B590B8','#7D6284'),('#C4AE8B','#8E704D','#5B4935'),
 ('#C4B3D1','#81669A','#513F67'),('#B7B4B0','#706D70','#424249'),('#C7B19A','#92745E','#5E4A3F'),
 ('#C8A486','#9C684C','#654331'),('#D8C7A1','#A7B77C','#78815A'),('#E1C28B','#D89458','#9A5E3F'),
 ('#C29B78','#9A6047','#6B4133'),('#D7DCE4','#A9B5C6','#6F7D91'),('#E0A078','#B9573E','#73342F'),
 ('#B7C99C','#71915B','#49613F'),('#9FC8D0','#548FA4','#376477'),('#BCD7E4','#78ABC5','#4C7792'),
)
assert len(NAMES)==len(SWATCHES)==24

def snapshot():
    return {
      'schema':'plushbound.creator_palettes_catalog.v1',
      'count':24,
      'paid_render_count':0,
      'source_art_required':False,
      'ledger_backed_image_assets':False,
      'palettes':[{'palette_id':f'palette-{i:03d}','name':n,'swatches':list(s)} for i,(n,s) in enumerate(zip(NAMES,SWATCHES),1)]
    }

if __name__=='__main__':
    print(json.dumps(snapshot(),indent=2,sort_keys=True))
