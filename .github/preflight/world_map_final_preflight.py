#!/usr/bin/env python3
"""Fail-closed, zero-spend preflight for Plushbound maps/world FINAL production.

This script intentionally has no generation-provider, Modal, GPU, HTTP, or secrets
integration. It verifies only repository evidence and deterministic contracts.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / ".github" / "preflight" / "world_map_final_preflight_contract.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PREFLIGHT FAIL: {message}")


def disabled_env(name: str) -> bool:
    value = os.environ.get(name, "0").strip().lower()
    return value in {"", "0", "false", "no", "off", "disabled"}


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    contract = load_json(CONTRACT_PATH)
    require(contract["schema"] == "plushbound.world_map_final_preflight.v1", "unexpected schema")
    require(contract["lane"] == "maps_world_final", "unexpected lane")
    require(contract["status"] == "PREFLIGHT_ONLY_DISABLED", "preflight status must remain disabled")

    spend = contract["spend_gate"]
    require(spend["production_enabled"] is False, "production must be disabled")
    require(spend["paid_remote_execution_allowed"] is False, "paid remote execution must be disabled")
    require(spend["provider_calls_allowed"] == 0, "provider call allowance must be zero")
    require(spend["gpu_calls_allowed"] == 0, "GPU call allowance must be zero")
    require(spend["generation_jobs_allowed"] == 0, "generation job allowance must be zero")
    require(spend["automatic_full_production_authorized"] is False, "catalog-wide production must remain locked")
    require(disabled_env("PLUSHBOUND_PRODUCTION_ENABLED"), "PLUSHBOUND_PRODUCTION_ENABLED must be disabled")
    require(disabled_env("PLUSHBOUND_PAID_REMOTE_ENABLED"), "PLUSHBOUND_PAID_REMOTE_ENABLED must be disabled")

    creator_rule = contract["creator_lock"]
    creator = load_json(ROOT / creator_rule["contract"])
    require(creator["final_total"] == creator_rule["required_final_total"] == 24, "Creator outfits must remain exactly 24")
    require(creator["full_outfits_current_pass_closed"] is True, "Creator outfits current pass must remain closed")
    require(creator["catalog_remainder_deferred"] is True, "Creator remainder must remain deferred")
    require(creator["completion_verified"] is True, "Creator 24-outfit closeout must remain verified")

    completed = contract["completed_lane_locks"]
    guardian = load_json(ROOT / completed["guardians"]["path"])
    require(guardian["status"] == completed["guardians"]["required_status"], "Guardian lock status changed")
    require(guardian["archive"]["asset_count"] == completed["guardians"]["required_asset_count"], "Guardian asset count changed")
    require(guardian["policy"]["regeneration_for_recovery_forbidden"] is True, "Guardian regeneration protection missing")

    npc = load_json(ROOT / completed["npcs"]["path"])
    require(npc["status"] == completed["npcs"]["required_status"], "NPC lock status changed")
    require(npc["accepted_asset_count"] == completed["npcs"]["required_asset_count"], "NPC asset count changed")
    require(npc["redundant_regeneration_prohibited"] is True, "NPC regeneration protection missing")

    enemy = load_json(ROOT / completed["enemies"]["path"])
    require(enemy["expected_master_count"] == completed["enemies"]["required_asset_count"], "Enemy master count changed")
    require(enemy["fail_closed"] is True, "Enemy archive must remain fail-closed")

    regions = contract["canonical_regions"]
    require(len(regions) == 10, "canonical world region count must be 10")
    require(len(set(regions)) == len(regions), "canonical world regions must be unique")
    require(regions == enemy["regions"], "world preflight region IDs must match banked canonical enemy regions")

    manifest = contract["preflight_manifest"]
    require(len(manifest) == len(regions), "preflight manifest must cover every canonical region exactly once")
    require(len({entry["asset_id"] for entry in manifest}) == len(manifest), "manifest asset IDs must be unique")
    require({entry["region"] for entry in manifest} == set(regions), "manifest region coverage mismatch")
    for entry in manifest:
        require(entry["asset_id"] == f"world.{entry['region']}.environment_master", f"unstable asset ID for {entry['region']}")
        require(entry["role"] == "environment_master", f"unexpected role for {entry['region']}")

    # Import only the deterministic local preset definition. No provider/runtime import occurs.
    from modal_worker.production_presets import get_preset

    pipeline = contract["pipeline_contract"]
    preset = get_preset(pipeline["preset"])
    require(preset.width == pipeline["width"] == 1024, "environment width contract mismatch")
    require(preset.height == pipeline["height"] == 768, "environment height contract mismatch")
    require(preset.steps == pipeline["steps"] == 28, "environment step contract mismatch")
    require(preset.guidance_scale == pipeline["guidance_scale"] == 5.0, "environment guidance contract mismatch")
    require(pipeline["output_format"] == "PNG", "world output format must remain PNG")
    require(pipeline["final_tileset_lane_separate"] is True, "maps/world preflight must not silently absorb tileset production")

    paid_evidence = contract["existing_paid_environment_evidence"]
    require(paid_evidence["four_lane_gpu_canary_run_id"] > 0, "existing environment GPU canary evidence missing")
    require(paid_evidence["balanced_rehearsal_run_id"] > 0, "existing environment rehearsal evidence missing")
    require(paid_evidence["reuse_before_rerender"] is True, "paid evidence must be inspected/reused before rerender")

    policy = contract["policy"]
    require(policy["fail_closed"] is True, "preflight must remain fail-closed")
    require(policy["rerender_because_local_artifact_missing"] is False, "missing local files must not authorize rerender")
    require(policy["inspect_remote_paid_execution_evidence_first"] is True, "remote paid evidence inspection guard missing")
    require(policy["completed_lanes_read_only"] is True, "completed lanes must remain read-only")
    require(policy["creator_clothing_read_only_for_current_pass"] is True, "Creator clothing must remain closed")
    require(policy["preflight_may_not_call_network_generation_providers"] is True, "network generation must be prohibited")

    bounded = contract["post_preflight_bounded_strategy"]
    require(bounded["requires_green_preflight"] is True, "real production must require green preflight")
    require(bounded["first_real_wave_asset_cap"] == 8, "first real canary wave must remain capped at 8")
    require(bounded["hard_max_assets_per_wave"] == 384, "hard wave cap must remain 384")
    require(bounded["never_stack_paid_runs"] is True, "paid runs must never stack")
    require(bounded["stop_on_validation_failure"] is True, "validation failure must stop scaling")
    require(bounded["resume_without_regenerating_completed_asset_ids"] is True, "resume must skip completed IDs")

    report = {
        "schema": "plushbound.world_map_final_preflight_report.v1",
        "lane": contract["lane"],
        "status": "PASS_NO_SPEND",
        "production_skipped": True,
        "paid_remote_execution_skipped": True,
        "generation_calls": 0,
        "gpu_calls": 0,
        "provider_calls": 0,
        "manifest_count": len(manifest),
        "manifest_sha256": canonical_digest(manifest),
        "checks": {
            "spend_gate": "PASS",
            "creator_24_outfit_lock": "PASS",
            "completed_lane_evidence": "PASS",
            "canonical_regions": "PASS",
            "deterministic_manifest": "PASS",
            "environment_pipeline": "PASS",
            "geometry_1024x768": "PASS",
            "remote_paid_evidence_guard": "PASS",
            "bounded_strategy_guardrails": "PASS"
        },
        "next_gate": "bounded_real_source_canary_max_8_only_after_this_report_is_green"
    }
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
