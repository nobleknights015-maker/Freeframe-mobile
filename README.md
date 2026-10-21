# FreeFrame Mobile

FreeFrame Mobile is a local, Android-first AI image-generation app built around the open-source Local Diffusion / stable-diffusion.cpp stack. It is designed to run image generation directly on the phone without requiring a paid cloud service.

## Downloads

FreeFrame is published in two Android profiles:

- **FreeFrame Standard** — recommended for newer phones with about **8 GB or more of physical RAM**. Uses a 512×512 default generation profile at 20 steps.
- **FreeFrame Low Memory** — intended for phones with about **4–6 GB of physical RAM**. Uses a much smaller 320×320 default generation profile at 12 steps to reduce peak memory pressure.

The APKs are produced by the **Build FreeFrame Android APKs** GitHub Actions workflow. Open the latest successful workflow run and download either:

- `FreeFrame-standard-APK`
- `FreeFrame-low-memory-APK`

Each GitHub artifact downloads as a ZIP. Extract it, then install the APK inside.

> Android may ask you to allow installs from your browser or file-manager app because FreeFrame is not distributed through Google Play.

## What you need

FreeFrame does **not** bundle AI model weights. You need a compatible Stable Diffusion-family model file on your phone.

Supported model file types include:

- `.gguf`
- `.safetensors`
- `.ckpt`

For phones with limited RAM, quantized `.gguf` models such as Q4_0 are generally the most practical starting point.

Model files can be several gigabytes. Make sure your phone has enough free storage before downloading one.

## How to use FreeFrame

1. Install the APK that matches your phone.
2. Open FreeFrame.
3. Tap **Models**.
4. Choose a compatible model file stored on your phone.
5. Wait until FreeFrame reports that the model is loaded.
6. Type a prompt in the message box.
7. Tap generate/send.
8. When an image finishes, you can save it, retry the prompt, edit it, or use it as a reference for another generation.

You can also attach an image before submitting a prompt. FreeFrame prepares that image as a local reference for image-to-image/edit-style generation.

## Which APK should I use?

### Use Standard if

- your phone has roughly 8 GB or more of **physical** RAM;
- you have a recent mid-range or flagship Android device;
- you want the better default 512×512 generation size.

### Use Low Memory if

- your phone has 4–6 GB of physical RAM;
- Standard crashes when generation begins;
- Android kills FreeFrame while a model is loaded;
- you are willing to trade resolution for a better chance of finishing a generation.

Virtual RAM / RAM Boost is not equivalent to physical RAM. A phone advertised as “12 GB with RAM Boost” may still physically contain only 4 GB of RAM.

## Current status

FreeFrame is an **alpha/beta-stage project**. The interface, model loading, prompt entry, reference-image flow, saving, retrying, and native generation plumbing are implemented, but model compatibility and memory use vary significantly between Android devices.

The low-memory build is experimental. On some 4 GB phones, even a quantized model may still exceed the available memory when generation begins.

The Standard build is intended as the general public build for stronger Android hardware.

## Privacy and cost

FreeFrame's current public build performs generation **locally on the device**. It does not require an OpenAI API key or a paid image-generation server.

Your model choice may have its own license and usage terms. FreeFrame does not grant additional rights to third-party model weights.

## Building from source

The GitHub workflow reconstructs the app from a pinned Local Diffusion engine revision, overlays the FreeFrame app layer, applies the selected phone profile, runs Flutter analysis/tests, builds release APKs, and runs Android smoke tests.

The two profiles are generated from the same codebase:

| Build | Default size | Steps | Target hardware |
| --- | ---: | ---: | --- |
| Standard | 512×512 | 20 | ~8 GB+ physical RAM |
| Low Memory | 320×320 | 12 | ~4–6 GB physical RAM |

To build manually through GitHub:

1. Open **Actions**.
2. Select **Build FreeFrame Android APKs**.
3. Run the workflow.
4. Wait for the Standard and Low Memory build jobs and smoke tests to finish.
5. Download the desired APK artifact.

## Known limitations

- Large models can exceed Android memory limits even if the APK itself runs normally.
- Low-memory phones may need smaller or more aggressively quantized models.
- Generation speed depends heavily on the phone CPU and model.
- GPU acceleration varies by Android hardware and driver support; FreeFrame currently prioritizes the more predictable local CPU/native path.
- Reference-image processing and generated-image history still have room for further memory optimization.
- This is not yet a Play Store production release.

## Reporting problems

When reporting a crash, include:

- phone model;
- physical RAM amount;
- Android version;
- model filename/type and approximate file size;
- whether you used Standard or Low Memory;
- whether the crash happened while loading the model, choosing an image, or when generation began.

That information is much more useful than only saying that the app crashed.

## Upstream engine and ownership

FreeFrame Mobile is an independent project and does not claim ownership of the open-source projects or AI model weights it uses.

Primary upstream components include:

- **Local Diffusion** by rmatif — Apache License 2.0 — https://github.com/rmatif/Local-Diffusion
- **stable-diffusion.cpp** by leejet and contributors — MIT License — https://github.com/leejet/stable-diffusion.cpp
- **Flutter** by Google LLC and contributors — BSD 3-Clause License — https://github.com/flutter/flutter
- **Dart** by Google LLC and contributors — BSD 3-Clause License — https://github.com/dart-lang/sdk

FreeFrame Mobile includes FreeFrame-specific interface code, workflow files, integration changes, bug fixes, and other modifications/additions. Third-party code, trademarks, copyrights, and model weights remain the property of their respective owners.

See `NOTICE`, `LICENSE`, `THIRD_PARTY_NOTICES.md`, and `USER_RESPONSIBILITY.md` for attribution, licensing, and responsibility information.

## AI models

Model files are downloaded separately and are not owned by FreeFrame Mobile. Each checkpoint, LoRA, VAE, ControlNet model, or other model file remains subject to its own original license and usage terms. Quantizing or converting a model does not change its ownership or remove its original license obligations.
