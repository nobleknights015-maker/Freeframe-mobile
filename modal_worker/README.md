# FreeFrame Modal Worker

This directory is the cloud/headless counterpart to FreeFrame Mobile. It is intentionally isolated from the Android application so development cannot destabilize the published APKs.

## Purpose

- on-demand text-to-image inference;
- batch inference for the Plushbound asset library;
- persistent model caching in a Modal Volume;
- CPU-side asset integrity checks before/after GPU work;
- future image-to-image/inpainting and RPG Maker MV-specific validation;
- future ChatGPT/plugin-facing API surface.

## Current development model

The first deployment uses `stabilityai/sd-turbo` as a lightweight integration/test model on an NVIDIA L4. This is **not** a final Plushbound art model. It lets us benchmark the complete worker path before choosing larger weights and spending significant GPU credit.

Model weights are downloaded by Modal at runtime and cached in the `freeframe-model-cache` Volume. They are not committed to GitHub.

## Safety/cost choices

- GPU containers scale down after idle time instead of staying online continuously.
- `/health` and `/validate_asset` are CPU functions, so simple checks do not wake a GPU.
- one worker batch is capped at 32 requests to limit accidental oversized jobs;
- generation dimensions and step counts are bounded;
- validation inputs are capped at 32 MiB;
- the initial GPU profile is L4 so we can benchmark before considering more expensive hardware.

## Deploy

From an authenticated Modal development environment:

```bash
modal deploy modal_worker/freeframe_worker.py
```

Modal will build the image, create/reuse the model cache volume, and publish the web endpoints. The first GPU request downloads and caches the configured model.

The model can be overridden with the `FREEFRAME_MODEL` environment variable when we intentionally benchmark another compatible Diffusers checkpoint.

## Tests

The core tests intentionally avoid GPU inference and cover request validation and PNG serialization:

```bash
python -m unittest modal_worker/test_worker_core.py
```

GPU/model smoke tests are added after the first authenticated Modal deployment so they test the real runtime rather than pretending local CI has a GPU.

## Next milestones

1. authenticated Modal deployment and cold-start benchmark;
2. generation smoke test and output validation;
3. image-to-image/edit pipeline;
4. RPG Maker MV asset-profile validator;
5. resumable/checkpointed batch manifest;
6. parallel worker benchmark and cost projection;
7. secured ChatGPT-facing tool/API integration.
