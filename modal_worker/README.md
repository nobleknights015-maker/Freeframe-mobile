# FreeFrame Modal Worker

FreeFrame's cloud/headless worker is isolated from the Android app and handles generation, extraction, validation, reference storage, and Plushbound production planning.

## Plushbound Brain / Mini-Auren

`plushbound_brain.py` is the shared deterministic source of truth for asset-family contracts, required context, required outputs, pipeline state, and the catalog-wide production lock.

`mini_auren_controller.py` is the canonical controller name for the compact assistant integration. When present, it plans structured asset intents through the same `production_request_builder.py` used by batch generation. A future compact chat model can translate conversation into these intents, but it cannot override engine geometry, reference rights, family rules, or production authorization.

Authenticated CPU endpoints:

- `GET get_plushbound_brain` — current shared contract snapshot.
- `POST plan_asset_job` — validate/plan one structured asset intent without waking a GPU.
- `POST validate_asset` — inspect PNG/profile metadata.
- `POST store_reference` — persist an approved reference.

GPU endpoints:

- `POST generate_image` — render an already-built request.
- `POST extract_subject` — dedicated BiRefNet extraction.

The planner never starts the 22k+ catalog and always returns `automatic_full_production_authorized: false`.

## Living-fabric rule

Native Plushtopia creatures use one shared contract: **creature first, textile second**. Friendly Guardians are living companion species rather than retail toys; corrupted/boss Guardians preserve that biology under corruption; wild monsters remain feral living textile organisms rather than normal flesh-and-fur fantasy animals.

## Deployment and tests

The `freeframe-modal-worker` branch automatically recreates the worker when runtime/planner contract files change. Manual deployment remains available with:

```bash
modal deploy --strategy recreate modal_worker/freeframe_worker.py
```

Core CI compiles the worker and runs all `test_*.py` tests. GPU canaries are bounded and never authorize the full catalog.
