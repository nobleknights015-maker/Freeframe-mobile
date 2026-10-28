"""Zero-spend shadow activation proof for the current bounded V2 regional batch."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from modal_worker.world_asset_pipeline_v2_planner import build_rows, validate_paid_gate

STATE_PATH = Path("modal_worker/world_asset_pipeline_v2_state.json")
FREEZE_PATH = Path("modal_worker/world_asset_pipeline_v2_freeze.json")
TRIGGER_PATH = Path("modal_worker/world_asset_pipeline_v2_run_trigger.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_shadow_activation() -> dict:
    real_state = _load(STATE_PATH)
    real_freeze = _load(FREEZE_PATH)
    real_trigger = _load(TRIGGER_PATH)

    assert real_state["production_frozen"] is True
    assert real_state["paid_execution_enabled"] is False
    assert real_state["active_paid_region"] is None
    assert real_state["runtime_import_proof"] is True
    assert real_freeze["production_frozen"] is True
    assert real_freeze["paid_remote_execution_allowed"] is False
    assert real_freeze["runtime_import_proof"] is True
    assert real_trigger["enabled"] is False
    assert real_trigger["region"] is None
    assert real_trigger["requested_source_ids"] == []
    assert real_trigger["runtime_import_proof"] is True

    region = "silkspire"
    rows, plan = build_rows(region)
    ids = [row["asset_id"] for row in rows]
    requested_count = len(ids)
    if not 1 <= requested_count <= 8:
        raise RuntimeError("shadow batch expects 1..8 remaining Silkspire IDs")
    if plan["accepted_source_count"] + requested_count != 8:
        raise RuntimeError("shadow batch accounting does not resolve Silkspire to exact 8/8")
    if set(ids).intersection(plan["accepted_ids_excluded"]):
        raise RuntimeError("shadow batch includes an accepted Silkspire ID")

    shadow_state = deepcopy(real_state)
    shadow_state.update({
        "production_frozen": False,
        "paid_execution_enabled": True,
        "active_paid_region": region,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": True,
    })
    shadow_freeze = deepcopy(real_freeze)
    shadow_freeze.update({
        "production_frozen": False,
        "paid_remote_execution_allowed": True,
        "provider_calls_allowed": requested_count,
        "gpu_calls_allowed": requested_count,
        "generation_calls_allowed": requested_count,
        "catalog_wide_launch_authorized": False,
        "accepted_assets_immutable": True,
        "runtime_import_proof": True,
    })

    gate = validate_paid_gate(
        region,
        requested_count=requested_count,
        state_data=shadow_state,
        freeze_data=shadow_freeze,
    )
    assert gate["status"] == "PASS_PAID_GATE"
    assert gate["runtime_import_proof"] is True
    assert gate["receiver_contract_status"] == "PASS_ENGINE_V1_RECEIVER_RUNTIME_CONTRACT"
    assert gate["authorized_call_cap"] == requested_count
    assert gate["requested_count"] == requested_count

    assert _load(STATE_PATH) == real_state
    assert _load(FREEZE_PATH) == real_freeze
    assert _load(TRIGGER_PATH) == real_trigger

    return {
        "schema": "plushbound.world_asset_pipeline_v2_shadow_activation.v2",
        "status": "PASS_ZERO_SPEND_SHADOW_REGION_BATCH_AUTHORIZATION",
        "region": region,
        "accepted_source_count": plan["accepted_source_count"],
        "requested_source_ids": ids,
        "selected_generation_count": requested_count,
        "accepted_ids_excluded": plan["accepted_ids_excluded"],
        "authorized_call_cap": requested_count,
        "paid_gate_would_open": True,
        "real_production_remained_frozen": True,
        "credentials_exposed": False,
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "automatic_acceptance": False,
        "automatic_compile": False,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": True,
        "receiver_contract_status": gate["receiver_contract_status"],
    }


if __name__ == "__main__":
    print(json.dumps(run_shadow_activation(), indent=2, sort_keys=True))
