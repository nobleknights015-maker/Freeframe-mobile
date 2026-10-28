"""Zero-spend shadow activation proof for the first live V2 canary."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from modal_worker.world_asset_pipeline_v2_planner import build_rows, validate_paid_gate

STATE_PATH = Path("modal_worker/world_asset_pipeline_v2_state.json")
FREEZE_PATH = Path("modal_worker/world_asset_pipeline_v2_freeze.json")
TRIGGER_PATH = Path("modal_worker/world_asset_pipeline_v2_run_trigger.json")
CANARY_PATH = Path("modal_worker/world_asset_pipeline_v2_silkspire_live_canary_plan.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_shadow_activation() -> dict:
    real_state = _load(STATE_PATH)
    real_freeze = _load(FREEZE_PATH)
    real_trigger = _load(TRIGGER_PATH)
    canary = _load(CANARY_PATH)

    # The real repository must remain safely frozen while this proof runs.
    assert real_state["production_frozen"] is True
    assert real_state["paid_execution_enabled"] is False
    assert real_state["active_paid_region"] is None
    assert real_freeze["production_frozen"] is True
    assert real_freeze["paid_remote_execution_allowed"] is False
    assert real_trigger["enabled"] is False
    assert real_trigger["region"] is None
    assert real_trigger["requested_source_ids"] == []

    region = canary["region"]
    ids = list(canary["requested_source_ids"])
    assert region == "silkspire"
    assert ids == ["tileset.silkspire.a5.source.city_stone_paving"]
    assert canary["max_requested_assets"] == 1
    assert canary["generation_attempts_per_requested_id_cap"] == 1
    assert canary["automatic_acceptance"] is False
    assert canary["automatic_compile"] is False
    assert canary["catalog_wide_launch_authorized"] is False

    # Build hypothetical active gate state entirely in memory. No repo file is changed.
    shadow_state = deepcopy(real_state)
    shadow_state.update({
        "production_frozen": False,
        "paid_execution_enabled": True,
        "active_paid_region": region,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
    })
    shadow_freeze = deepcopy(real_freeze)
    shadow_freeze.update({
        "production_frozen": False,
        "paid_remote_execution_allowed": True,
        "provider_calls_allowed": 1,
        "gpu_calls_allowed": 1,
        "generation_calls_allowed": 1,
        "catalog_wide_launch_authorized": False,
        "accepted_assets_immutable": True,
    })

    gate = validate_paid_gate(region, state_data=shadow_state, freeze_data=shadow_freeze)
    rows, plan = build_rows(region, ids)
    assert gate["status"] == "PASS_PAID_GATE"
    assert len(rows) == 1
    assert [row["asset_id"] for row in rows] == ids
    assert plan["selected_generation_count"] == 1
    assert not set(ids).intersection(plan["accepted_ids_excluded"])
    assert rows[0]["input_state"] != "ACCEPTED"

    # Prove the real files were never modified by the shadow test.
    assert _load(STATE_PATH) == real_state
    assert _load(FREEZE_PATH) == real_freeze
    assert _load(TRIGGER_PATH) == real_trigger

    return {
        "schema": "plushbound.world_asset_pipeline_v2_shadow_activation.v1",
        "status": "PASS_ZERO_SPEND_SHADOW_LIVE_CANARY_AUTHORIZATION",
        "region": region,
        "requested_source_ids": ids,
        "selected_generation_count": 1,
        "accepted_ids_excluded": plan["accepted_ids_excluded"],
        "paid_gate_would_open": True,
        "real_production_remained_frozen": True,
        "credentials_exposed": False,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "automatic_acceptance": False,
        "automatic_compile": False,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_shadow_activation(), indent=2, sort_keys=True))
