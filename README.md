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

## Upstream engine and ownership

FreeFrame Mobile is an independent project and does not claim ownership of the open-source projects or AI model weights it uses.

Primary upstream components include:

- **Local Diffusion** by rmatif — Apache License 2.0  
  https://github.com/rmatif/Local-Diffusion
- **stable-diffusion.cpp** by leejet and contributors — MIT License  
  https://github.com/leejet/stable-diffusion.cpp
- **Flutter** by Google LLC and contributors — BSD 3-Clause License  
  https://github.com/flutter/flutter
- **Dart** by Google LLC and contributors — BSD 3-Clause License  
  https://github.com/dart-lang/sdk

FreeFrame Mobile includes FreeFrame-specific interface code, workflow files, integration changes, bug fixes, and other modifications/additions. Third-party code, trademarks, copyrights, and model weights remain the property of their respective owners.

See `NOTICE`, `LICENSE`, and `THIRD_PARTY_NOTICES.md` for attribution and license information.

## AI models

Model files are normally downloaded separately and are not owned by FreeFrame Mobile. Each checkpoint, LoRA, VAE, ControlNet model, or other model file remains subject to its own original license and usage terms. Quantizing or converting a model does not change its ownership or remove its original license obligations.
