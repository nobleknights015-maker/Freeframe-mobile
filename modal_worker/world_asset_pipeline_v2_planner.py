"""Zero-spend planner for the single World Asset Pipeline V2 generator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from modal_worker.world_asset_pipeline_v2_controller import plan_region, resolve_state

SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
STATE_PATH = Path("modal_worker/world_asset_pipeline_v2_state.json")
FREEZE_PATH = Path("modal_worker/world_asset_pipeline_v2_freeze.json")
RECEIVER_PATH = Path("modal_worker/world_asset_pipeline_v2_receiver_contract.json")
PROMPT_CONTRACT_VERSION = "regional-a5-material-swatch-v2"
WORKER_VERSION = "plushbound-world-asset-pipeline-v2-worker-v1"
MAX_BATCH_SIZE = 8


def _load(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"missing V2 input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _seed(asset_id: str, prompt_sha256: str) -> int:
    digest = hashlib.sha256(
        f"{WORKER_VERSION}:{asset_id}:{prompt_sha256}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def validate_receiver_contract(
    *,
    state_data: dict | None = None,
    freeze_data: dict | None = None,
    receiver_data: dict | None = None,
) -> dict:
    """Validate the banked game-side Engine v1 receiver proof in one place."""
    state = dict(state_data) if state_data is not None else _load(STATE_PATH)
    freeze = dict(freeze_data) if freeze_data is not None else _load(FREEZE_PATH)
    receiver = dict(receiver_data) if receiver_data is not None else _load(RECEIVER_PATH)

    if receiver.get("schema") != "plushbound.world_asset_pipeline_v2_receiver_contract.v1":
        raise RuntimeError("V2 receiver contract schema mismatch")
    if receiver.get("status") != "PASS_ENGINE_V1_RECEIVER_RUNTIME_GREEN":
        raise RuntimeError("V2 receiver runtime is not green")
    if receiver.get("runtime_import_proof") is not True:
        raise RuntimeError("V2 receiver runtime proof is not banked")
    if receiver.get("pipeline_resume_blocker") is not False:
        raise RuntimeError("V2 receiver still blocks production resume")
    if receiver.get("engine_profile") != "mv_tileset_a5":
        raise RuntimeError("V2 receiver engine profile drift")
    if receiver.get("sheet_size") != [384, 768]:
        raise RuntimeError("V2 receiver sheet geometry drift")
    if receiver.get("tile_size") != [48, 48] or receiver.get("grid") != [8, 16]:
        raise RuntimeError("V2 receiver tile/grid geometry drift")
    if receiver.get("slot_count") != 128:
        raise RuntimeError("V2 receiver slot contract drift")
    if receiver.get("accepted_assets_immutable") is not True:
        raise RuntimeError("V2 receiver does not preserve accepted-asset immutability")
    if receiver.get("missing_local_package_is_not_rerender_authority") is not True:
        raise RuntimeError("V2 receiver lost missing-package rerender protection")
    if receiver.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("V2 receiver must not authorize catalog-wide generation")
    if state.get("runtime_import_proof") is not True:
        raise RuntimeError("V2 state disagrees with banked receiver proof")
    if freeze.get("runtime_import_proof") is not True:
        raise RuntimeError("V2 freeze/gate disagrees with banked receiver proof")

    return {
        "status": "PASS_ENGINE_V1_RECEIVER_RUNTIME_CONTRACT",
        "runtime_import_proof": True,
        "profile": "mv_tileset_a5",
        "sheet_size": [384, 768],
        "tile_size": [48, 48],
        "grid": [8, 16],
        "slot_count": 128,
        "pipeline_resume_blocker": False,
        "catalog_wide_launch_authorized": False,
    }


def build_rows(region: str, requested_ids: list[str] | None = None) -> tuple[list[dict], dict]:
    plan = plan_region(region, requested_ids)
    selected = list(plan["selected_generation_ids"])
    if not selected:
        return [], plan
    if len(selected) > MAX_BATCH_SIZE:
        raise RuntimeError("V2 selected more than eight IDs")

    scope = _load(SCOPE_PATH)
    source = scope.get("source_contract", {})
    regional = scope.get("regions", {}).get(region)
    if not regional or regional.get("stable_sheet_id") != f"tileset.{region}.a5":
        raise RuntimeError(f"{region}: invalid regional scope")
    if source.get("prompt_contract_version") != PROMPT_CONTRACT_VERSION:
        raise RuntimeError("V2 prompt contract drift")
    if source.get("generation_attempts_per_material_cap") != 1:
        raise RuntimeError("V2 requires one attempt per requested asset")

    materials = list(regional.get("materials", []))
    labels = regional.get("material_prompt_labels", {})
    if len(materials) != 8 or set(labels) != set(materials):
        raise RuntimeError(f"{region}: invalid material label scope")
    required = [str(x).lower() for x in source.get("required_prompt_phrases", [])]
    if not required:
        raise RuntimeError("V2 anti-scene prompt requirements missing")

    resolved = resolve_state()["regions"][region]
    selected_set = set(selected)
    rows = []
    for material in materials:
        asset_id = f"tileset.{region}.a5.source.{material}"
        if asset_id not in selected_set:
            continue
        state = resolved["assets"][asset_id]
        if state["state"] == "ACCEPTED":
            raise RuntimeError(f"{asset_id}: accepted ID reached V2 planner")
        prompt = source["prompt_template"].format(
            region_material_hint=str(regional["region_material_hint"]),
            material_name=str(labels[material]),
        )
        if state.get("prompt_suffix"):
            prompt += " " + str(state["prompt_suffix"]).strip()
        if not all(term in prompt.lower() for term in required):
            raise RuntimeError(f"{asset_id}: anti-scene prompt contract incomplete")
        prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        rows.append({
            "asset_id": asset_id,
            "material_key": material,
            "region": region,
            "input_state": state["state"],
            "prompt": prompt,
            "prompt_sha256": prompt_sha,
            "prompt_contract_version": PROMPT_CONTRACT_VERSION,
            "seed": _seed(asset_id, prompt_sha),
        })

    if [row["asset_id"] for row in rows] != selected:
        raise RuntimeError("V2 planner order/scope disagrees with controller")
    if set(plan["accepted_ids_excluded"]).intersection(selected_set):
        raise RuntimeError("V2 planner overlaps accepted IDs")
    return rows, plan


def validate_paid_gate(
    region: str,
    *,
    state_data: dict | None = None,
    freeze_data: dict | None = None,
    receiver_data: dict | None = None,
) -> dict:
    """Validate the paid gate. Optional in-memory data enables zero-spend shadow tests."""
    state = dict(state_data) if state_data is not None else _load(STATE_PATH)
    freeze = dict(freeze_data) if freeze_data is not None else _load(FREEZE_PATH)
    receiver = validate_receiver_contract(
        state_data=state,
        freeze_data=freeze,
        receiver_data=receiver_data,
    )
    if freeze.get("production_frozen") is True or freeze.get("paid_remote_execution_allowed") is not True:
        raise RuntimeError("V2 generation remains frozen")
    if state.get("production_frozen") is True or state.get("paid_execution_enabled") is not True:
        raise RuntimeError("V2 state has not enabled generation")
    if state.get("active_paid_region") != region:
        raise RuntimeError("V2 generation is not bound to this region")
    if state.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("catalog-wide generation must remain disabled")
    if freeze.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("freeze manifest must keep catalog-wide generation disabled")
    if freeze.get("accepted_assets_immutable") is not True:
        raise RuntimeError("accepted-asset immutability gate is not asserted")
    if freeze.get("missing_local_artifact_is_not_rerender_authority") is not True:
        raise RuntimeError("missing local artifact protection is not asserted")
    return {
        "status": "PASS_PAID_GATE",
        "region": region,
        "one_region_only": True,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": True,
        "receiver_contract_status": receiver["status"],
    }


def paid_gate_open(region: str) -> None:
    validate_paid_gate(region)


def validate_rebuild_contract() -> dict:
    from modal_worker.production_pipeline import inspect_master

    state = _load(STATE_PATH)
    freeze = _load(FREEZE_PATH)
    if not state.get("production_frozen") or state.get("paid_execution_enabled"):
        raise RuntimeError("V2 rebuild validation expected frozen state")
    if not freeze.get("production_frozen") or freeze.get("paid_remote_execution_allowed"):
        raise RuntimeError("V2 rebuild validation expected frozen gate")
    receiver = validate_receiver_contract(state_data=state, freeze_data=freeze)
    gloamfen_rows, gp = build_rows("gloamfen")
    silkspire_rows, sp = build_rows("silkspire")
    if gloamfen_rows or gp["selected_generation_count"] != 0:
        raise RuntimeError("accepted Gloamfen IDs were not protected")
    if len(silkspire_rows) != 8 or sp["selected_generation_count"] != 8:
        raise RuntimeError("fresh Silkspire scope did not resolve to eight IDs")

    tileset_grid = inspect_master(
        asset_class="tileset_master",
        fmt="PNG",
        width=384,
        height=384,
        has_alpha=False,
        panel_grid_detected=True,
    )
    if not tileset_grid.accepted or tileset_grid.errors:
        raise RuntimeError("V2 tileset material grid policy incorrectly rejects periodic seams")
    if not any("grid-like periodicity permitted" in warning for warning in tileset_grid.warnings):
        raise RuntimeError("V2 tileset grid policy lost its manual-QA warning")

    character_grid = inspect_master(
        asset_class="character_master",
        fmt="PNG",
        width=384,
        height=384,
        has_alpha=False,
        panel_grid_detected=True,
    )
    if character_grid.accepted or "multi-panel or model-sheet composition detected" not in character_grid.errors:
        raise RuntimeError("V2 character grid policy no longer rejects model-sheet composition")

    return {
        "schema": "plushbound.world_asset_pipeline_v2_planner_validation.v1",
        "status": "PASS_ZERO_GPU_SHARED_GENERATOR_PLANNER",
        "gloamfen_selected": 0,
        "silkspire_selected": 8,
        "max_batch_size": MAX_BATCH_SIZE,
        "accepted_id_refusal": "PASS",
        "receiver_contract_status": receiver["status"],
        "tileset_panel_grid_policy": "WARN_MANUAL_QA",
        "character_panel_grid_policy": "REJECT",
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "production_frozen": True,
        "runtime_import_proof": True,
    }
