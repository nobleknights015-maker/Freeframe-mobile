# Plushbound World Tile Asset Standard V1

Status: LOCKED
Owner split: Vera = visual source art; deterministic compiler = geometry/layout/manifest; World Editor = strict consumer.

## 1. Reference art vs production runtime art

Premade showcase sheets (for example BASALT, CLIFF_STONE, SEA_GLASS, DRY_SAND) are VISUAL/DESIGN REFERENCES ONLY. They define material identity, motif vocabulary, useful role coverage, and desired variety.

They are not runtime sheets and must never be cropped/repacked directly into production output.

Production flow is:

reference/showcase sheet -> Vera recreates clean source art for named roles -> human visual approval -> approved-art manifest -> deterministic compiler -> locked runtime sheet + slot manifest -> World Editor/V1.

## 2. Runtime sheet contract

Canvas: 384 x 768 px
Format: PNG, RGB or RGBA
Tile size: 48 x 48 px
Grid: 8 columns x 16 rows
Total slots: 128
Origin: top-left (0,0)
Margins: 0
Padding: 0
Scaling after placement: forbidden
Decorative header/title/UI frame: forbidden
Text/labels/guides/borders: forbidden

Every runtime slot must begin at:
x = column * 48
y = row * 48

The compiler, never Vera/image generation, owns these coordinates.

## 3. Locked role bands

Slots are deterministic and role-based. V1 bands:

- slots 000-031: A1 floor/base material variants
- slots 032-055: A2 wall/vertical material variants
- slots 056-079: A3 edges/corners/transitions
- slots 080-103: A4 props/structural pieces
- slots 104-127: A5 variations/details/extras

A material does not need every slot to contain unique art. Unused slots are explicit `empty` entries in the manifest; slot positions never collapse or shift.

## 4. Source-art rules

Vera generates source art by named asset role, not by composing the final 384x768 sheet.

Each source must:
- correspond to one stable asset ID and one declared role
- be newly generated Plushbound artwork
- visually match the approved reference material identity
- remain readable after deterministic reduction/cropping to 48x48 where applicable
- be top-down/tileable/seamless where the role requires it
- avoid baked presentation framing, labels, decorative sheet UI, and arbitrary neighboring assets
- avoid relying on AI-guessed grid geometry

Source art may be larger than 48x48 for quality, but the compiler owns all final resizing/cropping/placement.

## 5. Manifest contract

Schema: `plushbound.world_tile_sheet.v1`

Required top-level fields:
- `schema`
- `template_version`: `WORLD_TILE_ASSET_V1`
- `sheet_id`
- `material_id`
- `canvas_width`: 384
- `canvas_height`: 768
- `tile_size`: 48
- `columns`: 8
- `rows`: 16
- `provenance`: `vera-chatgpt-approved`
- `generator_calls_allowed`: false
- `gpu_allowed`: false
- `slots`: exactly 128 entries

Each slot entry must contain:
- `slot_index` (0-127)
- `row` (0-15)
- `column` (0-7)
- `x`
- `y`
- `role` (`a1_floor`, `a2_wall`, `a3_edge_corner`, `a4_prop`, `a5_variation`, or `empty`)
- `asset_id` (stable ID or null for empty)
- `source_path` (approved source PNG or null for empty)

## 6. Compiler validation / fail-closed rules

Reject the sheet/package if any of the following is true:
- canvas is not exactly 384x768
- tile size is not exactly 48x48
- grid is not exactly 8x16
- slot count is not exactly 128
- any x/y coordinate differs from deterministic grid math
- any duplicate non-empty asset ID exists
- manifest template/schema version is unknown
- source provenance is not `vera-chatgpt-approved`
- `generator_calls_allowed` is not false
- `gpu_allowed` is not false
- source path is missing for a non-empty slot
- runtime output contains text, decorative header framing, or reference-sheet pixels

World Editor must reject mismatches. It must never infer or guess layout visually.

## 7. Approval designation

A source asset becomes eligible for compilation only after explicit visual approval. Approved designation fields:

- `approval_status`: `approved`
- `approval_designation`: `VERA_APPROVED_SOURCE_V1`
- `provenance`: `vera-chatgpt-approved`
- `production_authorized`: true

Reference/showcase art uses:
- `approval_status`: `reference_only`
- `production_authorized`: false

## 8. Example: cliff_stone

`cliff_stone` showcase/reference sheet is used to define the desired visual language and coverage only.

Production does NOT crop that sheet.

Instead Vera recreates role-specific source art such as:
- `cliff_stone.a1.base_01`
- `cliff_stone.a1.base_02`
- `cliff_stone.a2.wall_face_01`
- `cliff_stone.a3.outer_corner_01`
- `cliff_stone.a3.inner_corner_01`
- `cliff_stone.a4.rock_prop_01`
- `cliff_stone.a5.moss_variation_01`

After approval, the compiler places those sources into their locked slots and creates the 384x768 runtime sheet plus manifest.

## 9. Non-negotiable production rule

Vera makes the art. The compiler makes the sheet. The World Editor reads the manifest.

No generated image is allowed to substitute for the deterministic runtime sheet geometry.
