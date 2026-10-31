# Plushbound World Tile Asset Standard V1

Status: LOCKED
Owner split: Vera = visual source art; deterministic compiler = geometry/layout/manifest; World Editor = strict consumer.

## 1. Production flow

Reference/showcase sheets define visual identity only. They are never runtime pixel sources.

Locked production flow:

reference/showcase sheet -> Vera creates new role-specific source art -> visual approval -> immutable approved-art PNG -> WORLD_TILE_ASSET_V1 manifest -> deterministic compiler -> structural validation -> deterministic production package export -> World Editor handoff gate -> World Editor / Engine v1

Reference-sheet pixels may never be cropped, extracted, normalized, wrapped, repacked, or promoted into runtime output.

## 2. Runtime sheet contract

- Canvas: 384 x 768 px
- Format: PNG, RGB or RGBA
- Tile size: 48 x 48 px
- Grid: 8 columns x 16 rows
- Total slots: 128
- Origin: top-left (0,0)
- Margins/padding: 0
- Resizing/resampling/cropping after visual approval: forbidden
- Decorative header/title/UI frame: forbidden
- Text/labels/guides/borders: forbidden

Every slot begins at:

`x = column * 48`
`y = row * 48`

The compiler, never image generation, owns these coordinates.

## 3. Locked role bands

- slots 000-031: `a1_floor`
- slots 032-055: `a2_wall`
- slots 056-079: `a3_edge_corner`
- slots 080-103: `a4_prop`
- slots 104-127: `a5_variation`

Unused slots remain explicit `empty` entries. Slot positions never collapse or shift.

## 4. Immutable source-art footprints

Production-approved source PNGs must already match one supported footprint exactly:

- `[1,1]` = 48 x 48 px
- `[2,2]` = 96 x 96 px

The deterministic compiler performs zero resizing, zero resampling, zero cropping, zero wrap-offset derivation, and zero visual repair.

A 2x2 source uses one anchor slot. The other three occupied grid cells must explicitly declare `covered_by` with the anchor asset ID. A 2x2 footprint may not leave the 8x16 grid, overlap another source, wrap rows, or cross a locked role-band boundary.

`target_size` is forbidden in WORLD_TILE_ASSET_V1 production manifests.

## 5. Approval contract

Every production anchor source requires:

- `approval_status`: `approved`
- `approval_designation`: `VERA_APPROVED_SOURCE_V1`
- `provenance`: `vera-chatgpt-approved`
- `production_authorized`: true

Reference/showcase art uses `approval_status: reference_only` and `production_authorized: false` and is not compiler-eligible.

## 6. Manifest contract

Schema: `plushbound.world_tile_sheet.v1`
Template: `WORLD_TILE_ASSET_V1`

Required top-level fields:

- `schema`
- `template_version`
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
- `slots`: exactly 128 entries in slot-index order

Every slot contains deterministic geometry:

- `slot_index` 0-127
- `row` 0-15
- `column` 0-7
- `x`
- `y`
- `role`
- `asset_id`
- `source_path`

Anchor slots additionally carry `footprint_tiles` and approval fields.

Covered cells carry:

- their normal role-band role
- `asset_id: null`
- `source_path: null`
- `covered_by: <anchor asset_id>`

Empty cells carry:

- `role: empty`
- `asset_id: null`
- `source_path: null`
- no `covered_by`

## 7. Fail-closed compiler rules

Reject if any of the following occurs:

- canvas/grid/tile geometry differs from 384x768 / 8x16 / 48x48
- slot count is not exactly 128
- slot order, row, column, x, or y differs from deterministic grid math
- a non-empty role does not match its locked role band
- duplicate non-empty stable asset IDs exist
- schema/template version is unknown
- provenance or approval designation is invalid
- production authorization is absent or false
- generator or GPU authorization is enabled
- a source path or source PNG is missing
- source dimensions do not exactly match the declared 1x1 or 2x2 footprint
- any resize/crop/derived-variant directive is requested
- 2x2 coverage is missing, orphaned, overlapping, out of bounds, or crosses a role band
- undeclared source PNGs are supplied to compilation
- reference/showcase pixels are used as production art

The World Editor must reject any mismatch. It must never infer layout visually.

## 8. Production export package

The authorized exporter is `modal_worker/world_tile_package_exporter.py`.

Each exported production package is one deterministic directory named from the locked material ID and sheet ID. It must contain exactly these five files and no extras:

- `runtime.png`
- `manifest.json`
- `compiler-metadata.json`
- `world-editor-handoff.json`
- `package.json`

The exporter must validate the compiled PNG, manifest, and compiler metadata through `modal_worker/world_editor_tile_ingest_gate.py` before publishing the directory. JSON serialization is canonical and deterministic. Existing packages are fail-closed by default and may only be replaced with an explicit overwrite operation after the replacement package passes validation.

`package.json` is an index, not an alternate source of truth. It records package schema/version, IDs, canonical filenames, compiler identity, handoff status, and the PNG/manifest integrity hashes already established by the compiler.

The exporter performs no image generation, resizing, cropping, resampling, pixel placement, visual inference, or repair.

## 9. World Editor handoff boundary

The authorized repository-side handoff gate is `modal_worker/world_editor_tile_ingest_gate.py`.

The World Editor must consume the package's `runtime.png`, `manifest.json`, and `compiler-metadata.json` together. The embedded `world-editor-handoff.json` must match a fresh canonical validation result. A PNG by itself is never production-authorized input.

The repository does not contain the live World Editor importer, so repository validation proves package integrity and Engine v1 compatibility only; it does not claim live runtime import proof.

## 10. Retired legacy path

The historical regional A5 path that derived sixteen 48x48 variants from each 384x384 material master is retained only for synthetic regression fixtures. It is not production-authorized and may not process real Plushbound runtime art.

Production runtime sheets use `modal_worker/a5_tilesheet_compiler.py` and the locked WORLD_TILE_ASSET_V1 manifest contract.

## 11. Non-negotiable rule

Vera makes and visually approves the source art. The compiler places immutable approved pixels. The exporter serializes the validated package. The World Editor consumes the locked package and manifest.

A technically valid sheet is not automatically a visually approved sheet.
