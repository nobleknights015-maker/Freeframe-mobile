# FreeFrame Mobile

FreeFrame Mobile is an Android-first, fully local image-generation project built around the open-source Local Diffusion engine.

## Current first build

The first milestone is intentionally simple and reliable:

- runs image generation on-device
- supports Stable Diffusion-family models supported by the underlying engine
- includes img2img, inpainting/outpainting, ControlNet, LoRA and PhotoMaker/reference-image capabilities inherited from the engine
- builds an installable Android APK in GitHub Actions
- keeps the APK small by downloading model files separately

## Build the APK

1. Open the repository on GitHub.
2. Open **Actions**.
3. Choose **Build FreeFrame Mobile APK**.
4. Tap **Run workflow**.
5. When the build finishes, open the run and download the **FreeFrame-Mobile-APK** artifact.
6. Extract the ZIP on Android and install `FreeFrame-Mobile.apk`.

Android may ask you to allow installs from your browser/files app because this APK is not coming from the Play Store.

## Current status

This is the first installable baseline. The next FreeFrame-specific layer will focus on:

- simplified mobile UI
- FreeFrame policy checks
- clearer reference-image controls
- saved character/reference profiles
- model presets suitable for phone RAM limits

## Upstream engine

The build currently pulls the Apache-2.0 Local Diffusion project by rmatif at build time and applies FreeFrame branding. This keeps the first build maintainable while FreeFrame-specific interface changes are developed.
