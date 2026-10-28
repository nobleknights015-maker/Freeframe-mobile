from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCOPE = Path('modal_worker/tileset_regional_a5_scope_manifest.json')
READINESS = Path('modal_worker/tileset_regional_a5_semantic_readiness_2026-10-28.json')
PROMPT_CONTRACT_VERSION = 'regional-a5-material-swatch-v2'
DEFAULT_REGION = 'silkspire'
DEFAULT_MATERIAL = 'pale_masonry'


def load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f'missing evidence: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def build(region: str, material: str) -> dict:
    scope = load(SCOPE)
    readiness = load(READINESS)
    checks: dict[str, str] = {}

    if scope.get('schema') != 'plushbound.tileset_regional_a5_scope_manifest.v1':
        raise RuntimeError('unexpected scope schema')
    if readiness.get('schema') != 'plushbound.tileset_regional_a5_semantic_readiness.v1':
        raise RuntimeError('unexpected semantic readiness schema')

    regional = scope['regions'].get(region)
    if not isinstance(regional, dict):
        raise RuntimeError('unknown region')
    if regional.get('status') != 'PREFLIGHT_PENDING':
        raise RuntimeError('fresh canary refuses closed, quarantined, repaired, or otherwise non-fresh region')
    checks['fresh_region_state'] = 'PASS'

    priorities = {row['region']: row for row in readiness.get('fresh_region_priority', [])}
    ranked = priorities.get(region)
    if not ranked:
        raise RuntimeError('region lacks semantic readiness ranking')
    if region == DEFAULT_REGION:
        if ranked.get('priority') != 1 or ranked.get('risk') != 'low':
            raise RuntimeError('locked first fresh canary is no longer the lowest-risk ranked region')
        if readiness.get('next_fresh_paid_candidate_after_shared_paid_lane_is_clear') != region:
            raise RuntimeError('semantic readiness no longer selects the locked first fresh canary region')
    checks['semantic_readiness_rank'] = 'PASS'

    materials = regional.get('materials', [])
    labels = regional.get('material_prompt_labels', {})
    if material not in materials or set(labels) != set(materials):
        raise RuntimeError('canary material is outside locked stable source scope')
    asset_id = f'tileset.{region}.a5.source.{material}'
    if material in set(ranked.get('watch_items', [])):
        raise RuntimeError('first fresh canary must not use a semantic watch-item source')
    checks['stable_source_and_non_watch_item'] = 'PASS'

    source = scope['source_contract']
    if source.get('prompt_contract_version') != PROMPT_CONTRACT_VERSION:
        raise RuntimeError('prompt contract drift')
    if source.get('generation_attempts_per_material_cap') != 1:
        raise RuntimeError('generation attempt cap drift')
    hint = str(regional.get('region_material_hint', '')).strip()
    forbidden = [str(x).lower() for x in source.get('forbidden_region_hint_terms', [])]
    hint_lower = hint.lower()
    if any(term in hint_lower for term in forbidden):
        raise RuntimeError('region material hint contains forbidden scene term')
    prompt = str(source['prompt_template']).format(
        region_material_hint=hint,
        material_name=labels[material],
    )
    required = [str(x).lower() for x in source.get('required_prompt_phrases', [])]
    if not required or not all(phrase in prompt.lower() for phrase in required):
        raise RuntimeError('rendered canary prompt fails repaired anti-scene contract')
    checks['prompt_contract_v2'] = 'PASS'
    checks['rendered_prompt_anti_scene_contract'] = 'PASS'

    if scope['spend_gate'].get('catalog_wide_launch_authorized') is not False:
        raise RuntimeError('catalog-wide launch unexpectedly authorized')
    if scope['spend_gate'].get('never_stack_paid_runs') is not True:
        raise RuntimeError('paid-run stacking lock drift')
    if scope['spend_gate'].get('one_region_per_paid_trigger') is not True:
        raise RuntimeError('one-region paid trigger lock drift')
    checks['global_spend_locks'] = 'PASS'

    return {
        'schema': 'plushbound.tileset_regional_a5_fresh_canary_preflight.v1',
        'status': 'PASS_NO_SPEND_FRESH_CANARY_READY_FOR_EXPLICIT_TRIGGER',
        'region': region,
        'material_key': material,
        'asset_id': asset_id,
        'stable_sheet_id': regional['stable_sheet_id'],
        'risk': ranked['risk'],
        'priority': ranked['priority'],
        'prompt_contract_version': PROMPT_CONTRACT_VERSION,
        'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'prompt': prompt,
        'asset_cap': 1,
        'generation_attempts_per_asset_cap': 1,
        'one_region_only': True,
        'one_source_only': True,
        'manual_visual_qa_required_before_any_continuation': True,
        'automatic_remaining_seven_authorized': False,
        'compile_authorized': False,
        'deterministic_finalize_authorized': False,
        'catalog_wide_launch_authorized': False,
        'production_skipped': True,
        'paid_remote_execution_skipped': True,
        'provider_calls': 0,
        'gpu_calls': 0,
        'generation_calls': 0,
        'runtime_import_proof': False,
        'checks': checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', default=DEFAULT_REGION)
    parser.add_argument('--material', default=DEFAULT_MATERIAL)
    args = parser.parse_args()
    print(json.dumps(build(args.region, args.material), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
