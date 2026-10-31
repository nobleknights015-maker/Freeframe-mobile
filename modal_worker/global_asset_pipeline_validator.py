from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

SCHEMA = "plushbound.global_asset_pipeline.v1"
PIPELINE_ID = "PLUSHBOUND_GLOBAL_ASSET_PIPELINE_V1"
REQUIRED_CLASSES = {
    "tileset_a1", "tileset_a2", "tileset_a3", "tileset_a4", "tileset_a5", "tileset_bcde",
    "field_characters", "faces_portraits", "sv_actors", "enemies", "sv_enemies", "animations",
    "battlebacks", "parallaxes", "system_ui", "titles", "icons_items_equipment",
    "character_creation_layers", "map_props_buildings", "quest_markers_and_world_ui",
    "audio_bgm", "audio_bgs", "audio_me", "audio_se",
}
FORBIDDEN_PRIMARY_SCOPES = {"tideglass", "silkspire", "foundry", "region"}


def validate_global_asset_pipeline(data: Mapping[str, object]) -> None:
    if data.get("schema") != SCHEMA:
        raise ValueError("global asset pipeline schema mismatch")
    if data.get("pipeline_id") != PIPELINE_ID:
        raise ValueError("global asset pipeline id mismatch")
    if data.get("scope") != "all_plushbound_runtime_assets":
        raise ValueError("pipeline scope must cover all Plushbound runtime assets")
    if data.get("primary_partition") != "asset_class":
        raise ValueError("asset_class must be the primary production partition")
    if data.get("region_is_metadata_only") is not True:
        raise ValueError("regions must be metadata only")
    if data.get("single_region_may_not_define_global_rules") is not True:
        raise ValueError("single regions may not define global production rules")
    if data.get("external_reference_pixels_allowed_in_runtime") is not False:
        raise ValueError("external reference pixels may not enter runtime")
    if data.get("external_reference_cropping_repacking_tracing_allowed") is not False:
        raise ValueError("external reference pixel derivation must remain forbidden")
    if data.get("original_plushbound_art_required") is not True:
        raise ValueError("original Plushbound art must be required")
    if data.get("visual_approval_required") is not True or data.get("sha256_attestation_required") is not True:
        raise ValueError("visual approval and SHA256 attestation must be required")

    classes = data.get("asset_classes")
    if not isinstance(classes, list):
        raise ValueError("asset_classes must be a list")
    ids = []
    for row in classes:
        if not isinstance(row, dict):
            raise ValueError("asset class entries must be objects")
        class_id = row.get("id")
        if not isinstance(class_id, str) or not class_id:
            raise ValueError("every asset class needs a non-empty id")
        ids.append(class_id)
        owner = row.get("production_owner")
        unit = row.get("generation_unit")
        if not isinstance(owner, str) or not owner:
            raise ValueError(f"{class_id}: missing production_owner")
        if not isinstance(unit, str) or not unit:
            raise ValueError(f"{class_id}: missing generation_unit")
        if class_id.lower() in FORBIDDEN_PRIMARY_SCOPES:
            raise ValueError(f"region-specific class forbidden in global registry: {class_id}")

    if len(ids) != len(set(ids)):
        raise ValueError("asset class ids must be unique")
    missing = REQUIRED_CLASSES - set(ids)
    if missing:
        raise ValueError(f"global asset registry missing required classes: {sorted(missing)}")

    rules = data.get("global_generation_rules")
    if not isinstance(rules, dict):
        raise ValueError("global_generation_rules must be an object")
    required_true = {
        "one_asset_id_per_generation",
        "one_visual_function_per_generation",
        "reference_pixels_may_never_be_runtime_pixels",
    }
    required_false = {
        "mixed_asset_class_generation_allowed",
        "sheet_showcase_generation_allowed",
        "decorative_extras_without_declared_function_allowed",
        "production_authorized_before_visual_review",
    }
    for key in required_true:
        if rules.get(key) is not True:
            raise ValueError(f"global rule must be true: {key}")
    for key in required_false:
        if rules.get(key) is not False:
            raise ValueError(f"global rule must be false: {key}")


def validate_file(path: Path) -> None:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("global asset pipeline must be a JSON object")
    validate_global_asset_pipeline(data)


if __name__ == "__main__":
    validate_file(Path("approved_art/PLUSHBOUND_GLOBAL_ASSET_PIPELINE_V1.json"))
    print("GLOBAL_ASSET_PIPELINE=PASS")
