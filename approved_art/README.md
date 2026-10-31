# Plushbound Approved Art Lane

This is the only authorized production handoff for new Plushbound artwork.

## Source of artwork

Artwork is generated and visually approved in ChatGPT by Vera before it enters this repository.

Required provenance string: `vera-chatgpt-approved`.

Every production asset must also carry:

- `approval_status: approved`
- `approval_designation: VERA_APPROVED_SOURCE_V1`
- `production_authorized: true`

Reference/showcase images are never production-authorized and may not enter this lane.

## Processing contract

Approved-art processing is local, deterministic, CPU-only validation/copy work on the GitHub runner.

The approved-art lane must not call Modal, FLUX, Klein, diffusion, text-to-image, image-to-image, or any other generative/remote image service. GPU use is disabled by contract.

Approved pixels are immutable in this lane. Resizing, resampling, cropping, conversion, and visual repair are forbidden. The processor validates the approved PNG and copies its bytes exactly.

Valid declared source footprints for V1 are:

- `[1, 1]` = 48 x 48 px
- `[2, 2]` = 96 x 96 px

The declared footprint must match the PNG dimensions exactly. The downstream deterministic compiler owns placement on the 48 px runtime grid.

## Round structure

Each round lives under `approved_art/rounds/<round-id>/` and contains:

- Vera-approved PNG source files
- `manifest.json` using schema `plushbound.approved_art_round.v1`

The GitHub workflow `.github/workflows/process-approved-plushbound-art.yml` validates the manifest and processes the approved PNGs locally with `modal_worker/approved_art_processor.py` (the legacy directory name is retained for branch compatibility; the processor itself no longer imports or calls Modal).

## Safety contract

Every round manifest must include:

- `generator_calls_allowed: false`
- `gpu_allowed: false`
- `provenance: vera-chatgpt-approved`

Every asset must include its approval designation and an explicit `footprint_tiles` declaration.

Any round that does not satisfy these requirements fails before output is produced.
