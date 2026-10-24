"""Four-lane bounded Plushbound production round against validated master families.

This runner intentionally stays inside the production contracts already proven by the
current FreeFrame/Modal freeze: character, Guardian, enemy, and environment masters.
It does not force creator/UI/VFX/tile/audio assets through unsupported contracts.
"""
from __future__ import annotations

import base64
import json
import pathlib
import re
import time
from typing import Any

import modal

from modal_worker.production_inspector import inspect_generation
from modal_worker.production_request_builder import build_production_request
from modal_worker.production_retry_policy import DEFAULT_PRODUCTION_RETRY_POLICY

APP_NAME = "freeframe-max-production-round"
WORKER_APP = "freeframe-worker"
WORKER_CLASS = "FreeFrameProductionGenerator"
OUT_ROOT = "max-production-output"
VERSION = "plushbound-max-production-v1"
GPU_RATE_USD_PER_SECOND = 0.000222
ITEMS_PER_SHARD = 32

REGIONS = [
    "elyndor",
    "crownweave",
    "silkspire",
    "gloamfen",
    "verdancia",
    "tideglass-coast",
    "moonpatch-steppe",
    "sunspool-desert",
    "cinderreach",
    "frostlace",
]

REGION_BRIEFS = {
    "elyndor": "sunny flowered plains, pastoral roads, warm timber settlements and clear blue skies",
    "crownweave": "regal woven architecture, elevated civic roads, banners and polished stonework",
    "silkspire": "vertical artisan cityscape, silk canopies, narrow terraces and elegant workshop districts",
    "gloamfen": "misty wetlands, reed paths, moss-dark timber structures and luminous marsh plants",
    "verdancia": "lush green woodland settlements, cultivated groves, living hedges and mossy stone paths",
    "tideglass-coast": "bright sea cliffs, glassy tide pools, weathered harbor timber and salt-grass paths",
    "moonpatch-steppe": "wide moonlit grassland, stitched nomad waystations, pale stone markers and open horizons",
    "sunspool-desert": "sunlit ochre dunes, woven shade structures, caravan roads and wind-carved ruins",
    "cinderreach": "charcoal ridges, ember-lit industry, dark volcanic stone and resilient scrubland",
    "frostlace": "snowbound highlands, pale timber lodges, ice-blue stone and wind-swept alpine paths",
}

NPC_ROLES = [
    "road warden", "village courier", "field herbalist", "artisan traveler",
    "waystitch attendant", "market porter", "local guide", "wandering scholar",
]

GUARDIAN_FORMS = [
    "emberfox", "mossbun", "moonmoth", "cloudram", "pebbletoad", "riverotter",
    "acornmouse", "threadfin", "brambledeer", "sunlark", "mistcat", "stonehare",
    "reedwing", "glowmole", "starling", "duskferret",
]

ENEMY_FORMS = [
    "mossback prowler", "thornhide stalker", "duskmane hunter", "stonepaw ravine predator",
    "reedfang marsh prowler", "frostbrush highland hunter", "sunscale scrub stalker", "rootclaw forest hunter",
]

ENV_SCENES = [
    "main travel road", "village approach", "waystitch crossing", "wildflower field route",
    "river crossing", "hilltop overlook", "woodland edge", "ruined roadside shrine",
]

app = modal.App(APP_NAME)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-")


def _region_target(global_index: int, per_region: int, family: str) -> tuple[str, int]:
    if global_index < 1:
        raise ValueError("global_index must be positive")
    zero = global_index - 1
    region_number = zero // per_region
    if region_number >= len(REGIONS):
        raise IndexError(f"{family} production lane is complete")
    region = REGIONS[region_number]
    local_index = zero % per_region + 1
    return region, local_index


def _guardian_derivatives(index: int) -> list[str]:
    root = f"guardian/guardian-{index:03d}"
    return [
        f"{root}/overworld", f"{root}/portrait", f"{root}/silhouette",
        f"{root}/battle-idle", f"{root}/battle-action", f"{root}/battle-hurt",
        f"{root}/bond-expression", f"{root}/icon", f"{root}/field-interaction",
        f"{root}/resting-pose",
    ]


def _item(shard: int, global_index: int) -> dict[str, Any] | None:
    if shard == 0:
        try:
            region, local = _region_target(global_index, 128, "npc")
        except IndexError:
            return None
        role = NPC_ROLES[(global_index - 1) % len(NPC_ROLES)]
        prompt = (
            f"adult {region.replace('-', ' ').title()} {role}, one natural full-body humanoid NPC, "
            f"practical layered clothing suited to {REGION_BRIEFS[region]}, grounded local materials, useful travel gear, "
            "distinct readable silhouette, believable everyday resident rather than a heroic poster pose"
        )
        return {
            "asset_id": f"reg/{region}/npc-sprites/{local:03d}",
            "preset": "plushbound_character",
            "asset_class": "character_master",
            "prompt": prompt,
            "target_group": f"reg/{region}/npc-sprites/{local:03d}",
        }

    if shard == 1:
        if global_index > 96:
            return None
        form = GUARDIAN_FORMS[(global_index - 1) % len(GUARDIAN_FORMS)]
        prompt = (
            f"small living {form} Guardian companion species native to Plushtopia, expressive alert posture, "
            "woven biological textile hide, sparse natural seam lines, clear functional anatomy and locomotion, "
            "original friendly creature silhouette, subtle Thread magic accents, living creature not a retail toy"
        )
        return {
            "asset_id": f"guardian-master/guardian-{global_index:03d}",
            "preset": "plushbound_guardian",
            "asset_class": "guardian_master",
            "prompt": prompt,
            "target_group": f"guardian/guardian-{global_index:03d}",
            "derives_to": _guardian_derivatives(global_index),
        }

    if shard == 2:
        try:
            region, local = _region_target(global_index, 64, "enemy")
        except IndexError:
            return None
        form = ENEMY_FORMS[(global_index - 1) % len(ENEMY_FORMS)]
        prompt = (
            f"{region.replace('-', ' ').title()} {form}, hostile low nonhuman living-textile battle creature, "
            f"regionally adapted to {REGION_BRIEFS[region]}, woven or quilted biological hide, believable weight and locomotion, "
            "dangerous readable silhouette, single monster only"
        )
        return {
            "asset_id": f"reg/{region}/enemy-battle/{local:03d}",
            "preset": "plushbound_enemy",
            "asset_class": "enemy_master",
            "prompt": prompt,
            "target_group": f"reg/{region}/enemy-battle/{local:03d}",
        }

    if shard == 3:
        try:
            region, local = _region_target(global_index, 64, "environment")
        except IndexError:
            return None
        scene = ENV_SCENES[(global_index - 1) % len(ENV_SCENES)]
        prompt = (
            f"{region.replace('-', ' ').title()} {scene}, traversable fantasy JRPG battle environment with "
            f"{REGION_BRIEFS[region]}, coherent foreground middle-ground and background, clear pathing, no foreground hero"
        )
        return {
            "asset_id": f"reg/{region}/battlebacks/{local:03d}",
            "preset": "plushbound_environment",
            "asset_class": "environment_master",
            "prompt": prompt,
            "target_group": f"reg/{region}/battlebacks/{local:03d}",
        }

    raise ValueError("shard must be 0..3")


def _round_items(shard: int, round_number: int) -> list[dict[str, Any]]:
    start = (round_number - 1) * ITEMS_PER_SHARD + 1
    items: list[dict[str, Any]] = []
    for global_index in range(start, start + ITEMS_PER_SHARD):
        item = _item(shard, global_index)
        if item is None:
            break
        item["global_index"] = global_index
        item["round"] = round_number
        item["shard"] = shard
        item["seed"] = 120000 + shard * 100000 + global_index
        items.append(item)
    return items


def _run(shard: int, round_number: int) -> dict[str, Any]:
    if round_number < 1:
        raise ValueError("round_number must be at least 1")
    items = _round_items(shard, round_number)
    out_dir = pathlib.Path(OUT_ROOT) / f"round-{round_number:04d}" / f"shard-{shard}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not items:
        report = {
            "version": VERSION, "round": round_number, "shard": shard,
            "count": 0, "accepted": 0, "quarantined": 0,
            "lane_complete": True, "estimated_raw_generation_usd": 0.0, "assets": [],
        }
        (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return report

    generator = modal.Cls.from_name(WORKER_APP, WORKER_CLASS)()
    retry = DEFAULT_PRODUCTION_RETRY_POLICY
    results: list[dict[str, Any]] = []
    total_gpu_seconds = 0.0
    started = time.monotonic()

    for item in items:
        base_request = build_production_request(item["preset"], item["prompt"], seed=int(item["seed"]))
        accepted = False
        final: dict[str, Any] | None = None
        for attempt in range(1, retry.max_attempts + 1):
            request = retry.variant(base_request, attempt)
            try:
                payload = generator.generate.remote(request)
                total_gpu_seconds += float(payload.get("elapsed_seconds", 0.0))
                inspection = inspect_generation(item, payload)
                if not inspection.get("accepted", False):
                    final = {
                        "asset_id": item["asset_id"], "attempt": attempt,
                        "seed": request.get("seed"), "accepted": False,
                        "inspection": inspection,
                    }
                    continue
                raw = base64.b64decode(payload["image_base64"], validate=True)
                filename = _slug(item["asset_id"].replace("/", "__")) + ".png"
                path = out_dir / filename
                path.write_bytes(raw)
                final = {
                    "asset_id": item["asset_id"], "target_group": item.get("target_group"),
                    "derives_to": item.get("derives_to", []), "preset": item["preset"],
                    "asset_class": item["asset_class"], "attempt": attempt,
                    "seed": payload.get("seed"), "model": payload.get("model"),
                    "renderer_route": payload.get("renderer_route"),
                    "elapsed_seconds": payload.get("elapsed_seconds"),
                    "sha256": payload.get("sha256"), "bytes": payload.get("bytes"),
                    "width": payload.get("width"), "height": payload.get("height"),
                    "inspection": inspection, "accepted": True, "quarantined": False,
                    "path": str(path),
                }
                accepted = True
                break
            except Exception as exc:
                final = {
                    "asset_id": item["asset_id"], "attempt": attempt,
                    "seed": request.get("seed"), "accepted": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
        if final is None:
            final = {"asset_id": item["asset_id"], "accepted": False, "error": "no generation result"}
        if not accepted:
            final["quarantined"] = True
        results.append(final)
        (out_dir / "checkpoint.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    accepted_count = sum(1 for item in results if item.get("accepted"))
    report = {
        "version": VERSION,
        "mode": "MAX_MODE_4_LANE",
        "round": round_number,
        "shard": shard,
        "count": len(results),
        "accepted": accepted_count,
        "quarantined": len(results) - accepted_count,
        "completion_rate": accepted_count / len(results) if results else 1.0,
        "total_gpu_seconds": round(total_gpu_seconds, 3),
        "estimated_raw_generation_usd": round(total_gpu_seconds * GPU_RATE_USD_PER_SECOND, 6),
        "wall_seconds": round(time.monotonic() - started, 3),
        "lane_complete": len(items) < ITEMS_PER_SHARD,
        "automatic_catalog_wide_authorized": False,
        "assets": results,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


@app.local_entrypoint()
def main(shard: int, round_number: int = 1):
    report = _run(int(shard), int(round_number))
    summary = {k: v for k, v in report.items() if k != "assets"}
    print(json.dumps(summary, sort_keys=True))
