# FreeFrame default-model architecture

FreeFrame should behave as one studio with one active model selection.

## Persisted settings

Store:
- model file path
- quantization
- scheduler
- TAESD enabled/disabled
- VAE tiling enabled/disabled
- backend

These settings survive app restarts. If the model file no longer exists, FreeFrame must not crash; it should clear the active-model state and ask the user to choose a replacement.

## Runtime behavior

The actual native model cannot remain resident after Android kills the process. During one app session, however, the active model selection should be shared across generation modes and should not be cleared merely because the user changes work mode.

On a fresh app launch, restore the saved model settings and auto-load the default model once the UI is ready. While loading, keep the UI responsive and show a single non-modal loading state.

## Low-memory target

Target the Moto G (2025) 4 GB physical-RAM profile. Prefer one active model at a time, Q4_0 for the default SD 1.5 path, 512x512 defaults, and proactive image downscaling before RGB expansion.
