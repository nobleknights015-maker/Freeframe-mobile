"""Shared source of truth for Plushbound production planning.

This is intentionally deterministic data, not an LLM prompt. Jarvis-facing tools,
Mini-Jarvis, the mobile client, and batch automation can all read the same family
contracts and pipeline states. A small conversational model may translate natural
language into these intents later, but it never gets to invent the production rules.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

BRAIN_VERSION = "plushbound-brain-v1"
WORLD_NAME = "Plushtopia"
CATALOG_SCOPE = "22k+ replacement entries"

KNOWN_REGIONS = {
    "elyndor": {
        "display_name": "Elyndor",
        "identity": "sunny plains, connected woodland paths, stitched-fantasy settlements and Guardian habitats",
    },
}


@dataclass(frozen=True)
class AssetFamilyContract:
    family: str
    production_state: str
    production_preset: str | None
    creature_family: str | None
    required_context: tuple[str, ...]
    required_outputs: tuple[str, ...]
    rules: tuple[str, ...]

    def metadata(self) -> dict:
        data = asdict(self)
        data["required_context"] = list(self.required_context)
        data["required_outputs"] = list(self.required_outputs)
        data["rules"] = list(self.rules)
        return data


FAMILY_CONTRACTS: dict[str, AssetFamilyContract] = {
    "character_master": AssetFamilyContract(
        family="character_master", production_state="validated", production_preset="plushbound_character", creature_family=None,
        required_context=(), required_outputs=("master_art",),
        rules=("single adult character", "Plushtopia-native clothing and materials", "original design"),
    ),
    "guardian_friendly": AssetFamilyContract(
        family="guardian_friendly", production_state="candidate", production_preset="plushbound_guardian", creature_family="guardian_friendly",
        required_context=("region",), required_outputs=("master_art", "field_sprite", "battler", "icon_or_face"),
        rules=("living companion species", "creature first and textile second", "not a retail toy"),
    ),
    "guardian_corrupt": AssetFamilyContract(
        family="guardian_corrupt", production_state="candidate", production_preset="plushbound_guardian", creature_family="guardian_corrupt",
        required_context=("region",), required_outputs=("master_art", "field_sprite", "battler", "icon_or_face"),
        rules=("same living-fabric lineage as Guardians", "visible corruption and wear", "not a generic flesh monster"),
    ),
    "guardian_boss": AssetFamilyContract(
        family="guardian_boss", production_state="candidate", production_preset="plushbound_guardian", creature_family="guardian_boss",
        required_context=("region",), required_outputs=("master_art", "boss_battler", "field_or_event_sprite", "icon_or_face"),
        rules=("same living-fabric biology", "major threat silhouette", "ancient or lore-significant detailing"),
    ),
    "enemy_creature": AssetFamilyContract(
        family="enemy_creature", production_state="candidate", production_preset="plushbound_enemy", creature_family="enemy_creature",
        required_context=("region",), required_outputs=("master_art", "battler", "field_sprite_or_event_sprite"),
        rules=("living textile ecosystem", "feral hostile anatomy", "not an ordinary flesh-and-fur fantasy animal"),
    ),
    "enemy_human": AssetFamilyContract(
        family="enemy_human", production_state="planned", production_preset=None, creature_family=None,
        required_context=("region", "faction", "role", "guardian_relationship"), required_outputs=("master_art", "field_sprite", "battler_or_event_pose", "face"),
        rules=("human anatomy", "faction and livelihood visible in gear", "Plushtopia-native materials and symbols"),
    ),
    "environment_master": AssetFamilyContract(
        family="environment_master", production_state="validated", production_preset="plushbound_environment", creature_family=None,
        required_context=("region",), required_outputs=("master_art",),
        rules=("traversable JRPG readability", "region-specific architecture and vegetation", "original Plushbound language"),
    ),
    "mv_single_character": AssetFamilyContract(
        family="mv_single_character", production_state="validated", production_preset=None, creature_family=None,
        required_context=("source_asset_id",), required_outputs=("144x192_rgba_3x4_sheet",),
        rules=("exact editor geometry", "direction rows down left right up", "step phases left idle right"),
    ),
    "guardian_walk_sheet": AssetFamilyContract(
        family="guardian_walk_sheet", production_state="planned", production_preset=None, creature_family=None,
        required_context=("source_asset_id",), required_outputs=("editor_ready_walk_sheet",),
        rules=("species identity preserved across cells", "direction and phase consistency"),
    ),
    "portrait_face": AssetFamilyContract(
        family="portrait_face", production_state="planned", production_preset=None, creature_family=None,
        required_context=("source_asset_id",), required_outputs=("engine_ready_face_or_portrait",),
        rules=("identity lock", "readable expression", "exact target geometry"),
    ),
    "battler": AssetFamilyContract(
        family="battler", production_state="planned", production_preset=None, creature_family=None,
        required_context=("source_asset_id",), required_outputs=("engine_ready_battler",),
        rules=("battle-readable silhouette", "identity lock", "transparent background where required"),
    ),
    "icon": AssetFamilyContract(
        family="icon", production_state="planned", production_preset=None, creature_family=None,
        required_context=("source_asset_id",), required_outputs=("engine_ready_icon",),
        rules=("legible at engine scale", "simple focal silhouette"),
    ),
    "creator_layer": AssetFamilyContract(
        family="creator_layer", production_state="planned", production_preset=None, creature_family=None,
        required_context=("slot", "body_type"), required_outputs=("engine_ready_generator_layer",),
        rules=("deterministic alignment", "transparent background", "layer-safe edges"),
    ),
    "tileset_48px": AssetFamilyContract(
        family="tileset_48px", production_state="planned", production_preset=None, creature_family=None,
        required_context=("region", "tileset_role"), required_outputs=("48px_grid_tileset",),
        rules=("seamless adjacency", "engine grid exactness", "region visual language"),
    ),
    "ui": AssetFamilyContract(
        family="ui", production_state="planned", production_preset=None, creature_family=None,
        required_context=("ui_role",), required_outputs=("engine_ready_ui_asset",),
        rules=("legible", "consistent Plushbound motifs", "exact geometry"),
    ),
    "vfx": AssetFamilyContract(
        family="vfx", production_state="planned", production_preset=None, creature_family=None,
        required_context=("effect_role",), required_outputs=("engine_ready_vfx",),
        rules=("clean alpha", "frame consistency", "readable action timing"),
    ),
    "audio": AssetFamilyContract(
        family="audio", production_state="separate_pipeline", production_preset=None, creature_family=None,
        required_context=("audio_role",), required_outputs=("engine_ready_audio",), rules=("route outside image generator",),
    ),
}


def get_family_contract(family: str) -> AssetFamilyContract:
    try:
        return FAMILY_CONTRACTS[family]
    except KeyError as exc:
        raise ValueError(f"unknown Plushbound asset family: {family}") from exc


def missing_context(family: str, context: dict | None) -> list[str]:
    contract = get_family_contract(family)
    context = context or {}
    return [key for key in contract.required_context if not str(context.get(key, "")).strip()]


def brain_snapshot() -> dict:
    return {
        "brain_version": BRAIN_VERSION,
        "world": WORLD_NAME,
        "catalog_scope": CATALOG_SCOPE,
        "known_regions": KNOWN_REGIONS,
        "families": {name: contract.metadata() for name, contract in FAMILY_CONTRACTS.items()},
        "automatic_full_production_authorized": False,
    }
