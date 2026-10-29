# Plushbound Approved Art Lane

This is the only authorized production handoff for new Plushbound artwork.

## Source of artwork

Artwork is generated and visually approved in ChatGPT by Vera before it enters this repository.

Required provenance string: `vera-chatgpt-approved`.

## What Modal may do

Modal is authorized only for deterministic post-processing such as PNG normalization, resizing requested by the manifest, extraction, sheet assembly, validation, manifest generation, packaging, and compatibility checks.

Modal image generation is retired for Plushbound. The approved-art lane must not call FLUX, Klein, diffusion, text-to-image, image-to-image, or any other generative model. GPU use is disabled by contract for this lane.

## Round structure

Each round lives under `approved_art/rounds/<round-id>/` and contains:

- the Vera-approved PNG source files
- `manifest.json` using schema `plushbound.approved_art_round.v1`

The GitHub workflow `.github/workflows/process-approved-plushbound-art.yml` validates the manifest before exposing Modal credentials, then processes the approved PNGs with `modal_worker/approved_art_processor.py`.

## Safety contract

Every round manifest must include:

- `generator_calls_allowed: false`
- `gpu_allowed: false`
- `provenance: vera-chatgpt-approved`

Any round that does not satisfy these requirements must fail before Modal credentials are used.
