# Plushbound Approved Art Lane

This is the only authorized production handoff for new Plushbound artwork.

## Source of artwork

Artwork is generated and visually approved in ChatGPT by Vera before it enters this repository.

Required provenance: `vera-chatgpt-approved`.

Every production asset must carry:

- `approval_status: approved`
- `approval_designation: VERA_APPROVED_SOURCE_V1`
- `production_authorized: true`

Reference/showcase images are never production-authorized and may not enter this lane.

## Processing contract

Approved-art processing is local, deterministic, CPU-only validation/copy work on the GitHub runner.

The approved-art lane must not call Modal, FLUX, Klein, diffusion, text-to-image, image-to-image, or any other generative/remote image service. GPU use is disabled by contract.

Approved pixels are immutable after visual approval. Resizing, resampling, cropping, conversion, wrap-offset derivation, and visual repair are forbidden. The approved-art processor validates the PNG and copies its bytes exactly.

Valid declared source footprints for WORLD_TILE_ASSET_V1 are:

- `[1,1]` = 48 x 48 px
- `[2,2]` = 96 x 96 px

The footprint must match the PNG dimensions exactly. `target_size` is forbidden.

## Round structure

Each approved-art round uses schema `plushbound.approved_art_round.v1` and names only explicitly approved source PNGs.

The GitHub workflow `.github/workflows/process-approved-plushbound-art.yml` validates and processes approved PNGs locally with `modal_worker/approved_art_processor.py`. The legacy directory name remains for branch compatibility; the processor itself no longer imports or calls Modal.

## Runtime compilation

Approved sources enter runtime sheet assembly through `modal_worker/a5_tilesheet_compiler.py` using schema `plushbound.world_tile_sheet.v1` and template `WORLD_TILE_ASSET_V1`.

The compiler owns deterministic geometry, role bands, explicit empty/covered slots, placement, structural validation, hashing, and packaging. It performs zero resizing, cropping, resampling, source derivation, or visual repair.

A 2x2 source uses one anchor slot plus three explicit `covered_by` cells. It may not overlap, wrap out of bounds, or cross a locked role-band boundary.

The historical regional A5 compiler that derived sixteen 48x48 variants from each 384x384 material master is retained only for synthetic regression fixtures. It is explicitly not production-authorized.

The World Editor consumes the locked runtime PNG plus manifest and rejects mismatches; it never guesses layout visually.

## Safety contract

Every approved-art round must include:

- `generator_calls_allowed: false`
- `gpu_allowed: false`
- `provenance: vera-chatgpt-approved`

Every asset must include its approval designation and explicit footprint. Any violation fails before runtime compilation.
