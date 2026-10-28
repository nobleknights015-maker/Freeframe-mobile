"""Zero-spend planner for the single World Asset Pipeline V2 generator."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from modal_worker.world_asset_pipeline_v2_controller import plan_region, resolve_state

SCOPE_PATH = Path("modal_worker/tileset_regional_a5_scope_manifest.json")
STATE_PATH = Path("modal_worker/world_asset_pipeline_v2_state.json")
FREEZE_PATH = Path("modal_worker/world_asset_pipeline_v2_freeze.json")
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
) -> dict:
    """Validate the paid gate. Optional in-memory data enables zero-spend shadow tests."""
    state = dict(state_data) if state_data is not None else _load(STATE_PATH)
    freeze = dict(freeze_data) if freeze_data is not None else _load(FREEZE_PATH)
    if freeze.get("production_frozen") is True or freeze.get("paid_remote_execution_allowed") is not True:
        raise RuntimeError("V2 generation remains frozen")
    if state.get("production_frozen") is True or state.get("paid_execution_enabled") is not True:
        raise RuntimeError("V2 state has not enabled generation")
    if state.get("active_paid_region") != region:
        raise RuntimeError("V2 generation is not bound to this region")
    if state.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("catalog-wide generation must remain disabled")
    if state.get("runtime_import_proof") is not False:
        raise RuntimeError("runtime import proof must remain false during source generation")
    if freeze.get("catalog_wide_launch_authorized") is not False:
        raise RuntimeError("freeze manifest must keep catalog-wide generation disabled")
    if freeze.get("accepted_assets_immutable") is not True:
        raise RuntimeError("accepted-asset immutability gate is not asserted")
    return {
        "status": "PASS_PAID_GATE",
        "region": region,
        "one_region_only": True,
        "catalog_wide_launch_authorized": False,
        "runtime_import_proof": False,
    }


def paid_gate_open(region: str) -> None:
    validate_paid_gate(region)


def validate_rebuild_contract() -> dict:
    state = _load(STATE_PATH)
    freeze = _load(FREEZE_PATH)
    if not state.get("production_frozen") or state.get("paid_execution_enabled"):
        raise RuntimeError("V2 rebuild validation expected frozen state")
    if not freeze.get("production_frozen") or freeze.get("paid_remote_execution_allowed"):
        raise RuntimeError("V2 rebuild validation expected frozen gate")
    gloamfen_rows, gp = build_rows("gloamfen")
    silkspire_rows, sp = build_rows("silkspire")
    if gloamfen_rows or gp["selected_generation_count"] != 0:
        raise RuntimeError("accepted Gloamfen IDs were not protected")
    if len(silkspire_rows) != 8 or sp["selected_generation_count"] != 8:
        raise RuntimeError("fresh Silkspire scope did not resolve to eight IDs")
    return {
        "schema": "plushbound.world_asset_pipeline_v2_planner_validation.v1",
        "status": "PASS_ZERO_GPU_SHARED_GENERATOR_PLANNER",
        "gloamfen_selected": 0,
        "silkspire_selected": 8,
        "max_batch_size": MAX_BATCH_SIZE,
        "accepted_id_refusal": "PASS",
        "provider_calls": 0,
        "gpu_calls": 0,
        "generation_calls": 0,
        "production_frozen": True,
        "runtime_import_proof": False,
    }
