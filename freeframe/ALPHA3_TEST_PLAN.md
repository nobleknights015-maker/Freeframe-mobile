# FreeFrame Mobile Alpha 3 regression plan

Target device profile: Moto G (2025), 4 GB physical RAM, Android 15-class behavior, 128 GB storage.

A build is not considered ready for device testing until all automated checks pass three consecutive times.

## Critical flows

1. Default model persistence
   - select one model file
   - save path + quantization + scheduler + TAESD/VAE flags
   - reopen app and restore those settings
   - auto-load only when the saved model still exists
   - show a recoverable error if the file is missing

2. Shared active model session
   - one active model selection across Text-to-Image, Image-to-Image, Inpainting, Outpainting, PhotoMaker and Scribble
   - changing work mode must not silently clear the selected model
   - switching work mode must not create stacked navigation routes

3. Prompt focus
   - tap prompt
   - type at least 100 characters
   - edit text
   - hide/show keyboard
   - switch mode and return
   - prompt must not lose focus because of unrelated widget rebuilds or overlays

4. Image picking
   - cancel picker
   - choose portrait/landscape/square images
   - choose a large image; downscale before decoded RGB expansion
   - picker errors must return to an interactive page instead of leaving a modal overlay

5. Model loading / failure recovery
   - valid SD 1.5 safetensors + Q4_0
   - cancel model picker
   - unsupported file
   - missing file after it was previously saved as default
   - repeated load/unload
   - model initialization failure must always clear loading UI state

6. Navigation
   - repeated switching between every work mode
   - Android back button must not reveal stale generation pages underneath
   - no invisible modal route may remain after model/image picking

7. Repetition / memory
   - repeated image generation state cycles
   - repeated gallery selection cycles
   - ensure disposed page controllers/listeners do not retain stale state

## Build gate

CI must run `flutter analyze`, tests, regression source assertions, and APK compilation. The full workflow must pass three consecutive times before an APK is handed to the alpha tester.
