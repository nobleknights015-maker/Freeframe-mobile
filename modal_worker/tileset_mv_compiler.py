"""Deterministic RPG Maker MV tileset compiler for Plushbound Legends.

Visual generation owns source art only. This compiler owns final sheet dimensions,
slot coordinates, alpha handling, reserved cells, stable IDs, and validation. It never
resizes source blocks and never infers layout from pixels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

TILE = 48
CANONICAL_REGIONS = (
    "elyndor", "crownweave", "silkspire", "gloamfen", "verdancia",
    "tideglass-coast", "moonpatch-steppe", "sunspool-desert", "cinderreach", "frostlace",
)
SHEET_GEOMETRY = {
    "A1": (768, 576),
    "A2": (768, 576),
    "A3": (768, 384),
    "A4": (768, 720),
    "A5": (384, 768),
    "B": (768, 768),
    "C": (768, 768),
    "D": (768, 768),
    "E": (768, 768),
}


@dataclass(frozen=True)
class Slot:
    slot_id: str
    x: int
    y: int
    width: int
    height: int
    reserved_blank: bool = False

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)


def stable_sheet_id(region: str, sheet_type: str) -> str:
    return f"tileset.{region}.{sheet_type.lower()}"


def slots_for(sheet_type: str) -> list[Slot]:
    sheet_type = sheet_type.upper()
    if sheet_type not in SHEET_GEOMETRY:
        raise ValueError(f"unknown MV tileset sheet type: {sheet_type}")

    slots: list[Slot] = []
    if sheet_type == "A1":
        # Four 144px bands. Each band follows the locked MV A1 geometry:
        # 288px animated block, 96px special block, 288px animated block, 96px special block.
        for band in range(4):
            y = band * 144
            slots.extend([
                Slot(f"band{band:02d}_anim_left", 0, y, 288, 144),
                Slot(f"band{band:02d}_special_left", 288, y, 96, 144),
                Slot(f"band{band:02d}_anim_right", 384, y, 288, 144),
                Slot(f"band{band:02d}_special_right", 672, y, 96, 144),
            ])
    elif sheet_type == "A2":
        # Four 144px bands, each split into the locked 384px A/B halves.
        for band in range(4):
            y = band * 144
            slots.append(Slot(f"band{band:02d}_a", 0, y, 384, 144))
            slots.append(Slot(f"band{band:02d}_b", 384, y, 384, 144))
    elif sheet_type == "A3":
        # 8 x 4 autotile group-pattern blocks, each 96 x 96.
        for row in range(4):
            for col in range(8):
                slots.append(Slot(f"r{row:02d}_c{col:02d}", col * 96, row * 96, 96, 96))
    elif sheet_type == "A4":
        # 8 columns x 3 vertical groups. Each group is a 96x144 basic block
        # followed by a 96x96 group-pattern block: 240px per vertical group.
        for group in range(3):
            base_y = group * 240
            for col in range(8):
                x = col * 96
                slots.append(Slot(f"g{group:02d}_c{col:02d}_basic", x, base_y, 96, 144))
                slots.append(Slot(f"g{group:02d}_c{col:02d}_group", x, base_y + 144, 96, 96))
    elif sheet_type == "A5":
        for row in range(16):
            for col in range(8):
                slots.append(Slot(f"r{row:02d}_c{col:02d}", col * TILE, row * TILE, TILE, TILE))
    else:
        for row in range(16):
            for col in range(16):
                reserved = sheet_type == "B" and row == 0 and col == 0
                slots.append(Slot(f"r{row:02d}_c{col:02d}", col * TILE, row * TILE, TILE, TILE, reserved))
    return slots


def validate_layout(sheet_type: str) -> None:
    width, height = SHEET_GEOMETRY[sheet_type]
    slots = slots_for(sheet_type)
    seen_ids: set[str] = set()
    area = 0
    for slot in slots:
        if slot.slot_id in seen_ids:
            raise RuntimeError(f"{sheet_type}: duplicate slot id {slot.slot_id}")
        seen_ids.add(slot.slot_id)
        if any(v % TILE for v in (slot.x, slot.y, slot.width, slot.height)):
            raise RuntimeError(f"{sheet_type}:{slot.slot_id}: geometry is not aligned to {TILE}px")
        if slot.x < 0 or slot.y < 0 or slot.x + slot.width > width or slot.y + slot.height > height:
            raise RuntimeError(f"{sheet_type}:{slot.slot_id}: slot exceeds sheet bounds")
        area += slot.width * slot.height

    for i, left in enumerate(slots):
        lx1, ly1, lx2, ly2 = left.box
        for right in slots[i + 1:]:
            rx1, ry1, rx2, ry2 = right.box
            overlaps = lx1 < rx2 and lx2 > rx1 and ly1 < ry2 and ly2 > ry1
            if overlaps:
                raise RuntimeError(f"{sheet_type}: overlapping slots {left.slot_id} and {right.slot_id}")
    if area != width * height:
        raise RuntimeError(f"{sheet_type}: layout covers {area} pixels, expected {width * height}")
    if sheet_type == "B":
        blanks = [s for s in slots if s.reserved_blank]
        if len(blanks) != 1 or blanks[0].slot_id != "r00_c00":
            raise RuntimeError("B: top-left reserved blank slot contract is invalid")


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "plushbound.tileset_region_sheet_occupancy.v1":
        raise RuntimeError("unexpected tileset occupancy manifest schema")
    if data.get("tile_size") != [48, 48]:
        raise RuntimeError("tileset manifest tile size must be exactly 48x48")
    if tuple(data.get("canonical_regions", [])) != CANONICAL_REGIONS:
        raise RuntimeError("tileset manifest canonical region ordering changed")
    if set(data.get("sheet_geometry", {})) != set(SHEET_GEOMETRY):
        raise RuntimeError("tileset manifest sheet type set changed")
    for sheet_type, expected in SHEET_GEOMETRY.items():
        if tuple(data["sheet_geometry"][sheet_type]) != expected:
            raise RuntimeError(f"{sheet_type}: manifest geometry mismatch")
        validate_layout(sheet_type)

    regions = data.get("regions", {})
    if set(regions) != set(CANONICAL_REGIONS):
        raise RuntimeError("tileset manifest region set changed")
    phase1_count = 0
    phase2_count = 0
    all_ids: set[str] = set()
    for region in CANONICAL_REGIONS:
        row = regions[region]
        p1 = row.get("phase1", [])
        p2 = row.get("phase2", [])
        if len(p1) != len(set(p1)) or len(p2) != len(set(p2)):
            raise RuntimeError(f"{region}: duplicate sheet type in occupancy")
        if set(p1) & set(p2):
            raise RuntimeError(f"{region}: phase1 and phase2 overlap")
        if not set(p1 + p2) <= set(SHEET_GEOMETRY):
            raise RuntimeError(f"{region}: unknown sheet type in occupancy")
        phase1_count += len(p1)
        phase2_count += len(p2)
        for sheet_type in p1 + p2:
            asset_id = stable_sheet_id(region, sheet_type)
            if asset_id in all_ids:
                raise RuntimeError(f"duplicate stable sheet id: {asset_id}")
            all_ids.add(asset_id)

    counts = data.get("counts", {})
    if phase1_count != counts.get("phase1_expected_sheet_count"):
        raise RuntimeError(f"phase1 sheet count {phase1_count} does not match manifest")
    if phase2_count != counts.get("phase2_expected_sheet_count"):
        raise RuntimeError(f"phase2 sheet count {phase2_count} does not match manifest")
    if len(all_ids) != counts.get("final_expected_sheet_count"):
        raise RuntimeError(f"final sheet count {len(all_ids)} does not match manifest")
    if data.get("paid_generation_authorized") is not False:
        raise RuntimeError("occupancy manifest must remain no-spend until source-art canary is separately authorized")
    return data


def source_path(source_root: Path, region: str, sheet_type: str, slot: Slot) -> Path:
    return source_root / region / sheet_type / f"{slot.slot_id}.png"


def compile_sheet(region: str, sheet_type: str, source_root: Path, output_path: Path) -> dict:
    if region not in CANONICAL_REGIONS:
        raise RuntimeError(f"unknown region: {region}")
    sheet_type = sheet_type.upper()
    validate_layout(sheet_type)
    width, height = SHEET_GEOMETRY[sheet_type]
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    consumed = []
    for slot in slots_for(sheet_type):
        path = source_path(source_root, region, sheet_type, slot)
        if slot.reserved_blank:
            if path.exists():
                raise RuntimeError(f"{sheet_type}:{slot.slot_id}: reserved blank slot must not have a source file")
            continue
        if not path.is_file():
            raise RuntimeError(f"missing source block: {path}")
        with Image.open(path) as src:
            if src.size != (slot.width, slot.height):
                raise RuntimeError(
                    f"{sheet_type}:{slot.slot_id}: source size {src.size} must be exactly {(slot.width, slot.height)}; resizing is forbidden"
                )
            block = src.convert("RGBA")
            canvas.alpha_composite(block, (slot.x, slot.y))
        consumed.append(str(path))

    if sheet_type == "B":
        alpha = canvas.getchannel("A").crop((0, 0, TILE, TILE))
        if alpha.getbbox() is not None:
            raise RuntimeError("B: top-left tile is not fully transparent")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG")
    raw = output_path.read_bytes()
    with Image.open(output_path) as check:
        if check.size != (width, height) or check.mode != "RGBA":
            raise RuntimeError("compiled sheet failed output geometry/mode verification")
    return {
        "asset_id": stable_sheet_id(region, sheet_type),
        "region": region,
        "sheet_type": sheet_type,
        "width": width,
        "height": height,
        "tile_size": TILE,
        "source_block_count": len(consumed),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "output_path": str(output_path),
    }


def _write_source(path: Path, size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Opaque neutral test pixels; content is irrelevant to geometry validation.
    Image.new("RGBA", size, (127, 127, 127, 255)).save(path, format="PNG")


def self_test() -> dict:
    for sheet_type in SHEET_GEOMETRY:
        validate_layout(sheet_type)
    results = []
    with tempfile.TemporaryDirectory(prefix="plushbound-tileset-compiler-") as td:
        root = Path(td)
        source_root = root / "sources"
        output_root = root / "out"
        for sheet_type in ("A1", "A4", "B"):
            for slot in slots_for(sheet_type):
                if slot.reserved_blank:
                    continue
                _write_source(source_path(source_root, "elyndor", sheet_type, slot), (slot.width, slot.height))
            results.append(
                compile_sheet(
                    "elyndor",
                    sheet_type,
                    source_root,
                    output_root / f"elyndor_{sheet_type}.png",
                )
            )
        b = next(row for row in results if row["sheet_type"] == "B")
        with Image.open(b["output_path"]) as image:
            if image.getchannel("A").crop((0, 0, TILE, TILE)).getbbox() is not None:
                raise RuntimeError("self-test B blank tile verification failed")
    return {"status": "PASS", "compiled_test_sheets": 3, "layouts_validated": len(SHEET_GEOMETRY)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--region")
    parser.add_argument("--sheet-type")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    report = {
        "schema": "plushbound.tileset_mv_compiler_validation.v1",
        "manifest_valid": True,
        "tile_size": TILE,
        "sheet_geometry": {k: list(v) for k, v in SHEET_GEOMETRY.items()},
        "phase1_sheet_count": manifest["counts"]["phase1_expected_sheet_count"],
        "phase2_sheet_count": manifest["counts"]["phase2_expected_sheet_count"],
        "final_sheet_count": manifest["counts"]["final_expected_sheet_count"],
        "paid_generation_authorized": False,
    }
    if args.self_test:
        report["self_test"] = self_test()
    if not args.validate_only:
        if not all((args.region, args.sheet_type, args.source_root, args.output)):
            raise RuntimeError("compilation requires --region, --sheet-type, --source-root and --output")
        region_row = manifest["regions"].get(args.region)
        if not region_row:
            raise RuntimeError(f"region is not in occupancy manifest: {args.region}")
        sheet_type = args.sheet_type.upper()
        if sheet_type not in region_row["phase1"] + region_row["phase2"]:
            raise RuntimeError(f"{args.region}:{sheet_type} is inactive in occupancy manifest")
        report["compiled"] = compile_sheet(args.region, sheet_type, args.source_root, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
