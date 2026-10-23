# Plushbound FreeFrame production freeze — 2026-10-23

Status: **READY FOR EXPLICIT FULL-BATCH LAUNCH**

Automatic full-production authorization remains **false**. This freeze records that the bounded production evidence has passed; it does not silently start the 22k+ asset run.

## Frozen generation stack

- Model: `black-forest-labs/FLUX.2-klein-4B`
- GPU benchmark/rehearsal class: NVIDIA L4
- Production style policy: `style-policy-v4`
- Style profile version: `mt1.9`
- Character profile: `plushbound_trinity`
- Guardian profile: `plushbound_guardian_2d_candidate`
- Enemy profile: `plushbound_trinity_creature`
- Environment profile: `plushbound_trinity_environment`
- Subject extraction provider/model: `birefnet` / `ZhengPeng7/BiRefNet`
- MV single-character package geometry: 3x4 cells, 48x48 each, exact 144x192 RGBA PNG, `$` filename prefix

Any change to the model, production style policy/profile versions, presets, request builder, retry policy, extraction provider/model, normalizer, compositor, packaging geometry, or production factory invalidates this freeze and requires the affected bounded proof to be rerun.

## Evidence that passed

### 1. Evidence-backed character style lock

- Four-lane serialized Klein canary run: `39974097252`
- Reviewed character PNG SHA-256: `090ca99d917894ec59373907a8255b927029ebca6f1356706fab48798a9d4ccf`
- Receipt file: `approved_character_style_lock.py`
- Visual result: one full-body adult adventurer in one continuous scene; no turnaround/contact-sheet duplication or anatomy failure.

### 2. Four major asset lanes

Run `39974097252` completed real L4 generation for character, Guardian, enemy, and environment. Visual review passed all four lanes:

- character remained one full-body JRPG subject;
- Guardian remained one stitched 2D companion rather than a product-photo render;
- enemy remained a low quadruped monster rather than the previous humanoid/weapon drift;
- environment remained one coherent traversable scene rather than a collage/panel layout.

### 3. Current 32-asset production rehearsal

- GitHub Actions run: `39975668399`
- Artifact ID: `12510563985`
- Artifact ZIP digest: `sha256:cfdb0dbd9717bf5779f8ca783d022986bf4ace03259db6ca19b01b39a25c4f3c`
- Rehearsal version: `klein-rehearsal-32-v2-package-safe`
- Count: 32 (8 per major asset class)
- Accepted: 32/32
- Completion rate: 1.0
- Quarantined: 0
- Retry generations: 0
- Total measured generation GPU time: 83.716 seconds
- Wall time: 93.492 seconds
- Mean measured generation GPU time: ~2.616 seconds/image

All 32 outputs were visually reviewed. No character model-sheet regression, humanoid enemy regression, Guardian product-render regression, or environment collage regression was observed.

### 4. Current Klein subject extraction

- GitHub Actions run: `39978165957`
- Artifact ID: `12512346667`
- Artifact ZIP digest: `sha256:0ce939675a5bdddcb4b7e8e588d4d678b00736e5a71aea00d5fe20d2953a9c93`
- Smoke version: `current-klein-extraction-smoke-v2-production-runtime`
- Runtime dependency surface mirrors the production FreeFrame BiRefNet extractor.
- Inputs were the exact character, Guardian, and enemy outputs from rehearsal artifact `12510563985`.

Results:

- character: 768x1024 preserved, foreground fraction `0.263620`, edge alpha fraction `0.0`, output SHA-256 `cc3e81832af98865e2eb6dca63cc21003080f2d6a0075c98d6060560d7e99ead`;
- Guardian: 768x768 preserved, foreground fraction `0.241104`, edge alpha fraction `0.0`, output SHA-256 `f46dd0c9957457167f69ded564829fb7389a6b0068038087d412f659cd9e76d9`;
- enemy: 896x640 preserved, foreground fraction `0.344174`, edge alpha fraction `0.0`, output SHA-256 `4a372c455dd9e6c48381b8813b90eae26f682bda2fa5a3dc34a3134c899147ff`.

Visual inspection confirmed clean transparent subject silhouettes for all three current Klein samples.

### 5. Real GPU RPG Maker MV sheet canary

- Successful GitHub Actions run: `39977703274`
- Artifact ID: `12511588055`
- Artifact ZIP digest: `sha256:5182c6815bb9bf64a38f82ace2d85978c7ed16eb77c1a3b60f370ddc6a0e535d`
- Canary version: `plushbound-mv-sheet-canary-v2-reference-conditioned`
- Model: `black-forest-labs/FLUX.2-klein-4B`
- 1 canonical character reference + 12 reference-conditioned movement/direction frames
- Exact output: 144x192 RGBA PNG, 12 cells, `$` filename prefix
- Engine profile: `mv_single_character`
- Engine validation: valid, zero errors
- Factory version: `plushbound-production-factory-v1`
- Package version: `plushbound-mv-packager-v1`
- Final sheet SHA-256: `63dfabb644c29c85d05196b6cdce4bb98b657da26e62c632c286f9766b96aafa`

The generated sheet was visually inspected and retained the same dark-coat/gold-trim adventurer identity across the directional movement grid without multi-character collapse.

## Cost/readiness projection

The 32-asset rehearsal measured ~2.616 generation GPU-seconds per image. With the current L4 budget constant (`$0.000222/GPU-second`), raw generation for 22,000 assets projects to approximately **$12.78** before extraction, retries, storage, transfer, and other overhead. This remains below the existing $30 raw-generation target and $40 hard ceiling. The budget calculation by itself never authorizes production.

## Launch boundary

The bounded gates required before a full run have now passed:

- style lock: PASS
- four-lane real GPU canary: PASS
- 32-asset balanced rehearsal: PASS (32/32, zero quarantine)
- current subject extraction: PASS
- real editor-ready MV package canary: PASS
- retry/checkpoint/sharding/factory/inspector automated tests: PASS in worker CI

Therefore this frozen configuration is **ready for an explicit full-batch launch**.

`automatic_full_production_authorized = false`

The 22k+ run must remain checkpointed/sharded/resumable, must quarantine failed assets instead of poisoning the batch, and must not regenerate already-completed asset IDs after resume. A future configuration change invalidates the relevant evidence above before another large launch.
