# FreeFrame Rework

This branch replaces the patch-by-patch UI strategy with a FreeFrame-owned app layer.

## Product direction

- Chat-first interface with neutral light/dark themes.
- One shared model session for Text-to-Image, Img2Img, Inpainting, Outpainting and references.
- One persistent default model selected once by the user.
- FreeFrame interprets natural-language creative requests and maps them to generation operations.
- Technical controls are hidden behind an Advanced panel instead of being required for normal use.
- Image attachment, reference role selection, generation results and follow-up edits live in the conversation flow.

## Architecture

### FreeFrameShell
Owns app navigation, conversation state, theme, model status and back-button behavior. Tools are modes, not separate Navigator routes.

### ModelSessionManager
Owns the single native stable-diffusion context/worker. States: unloaded, loading, ready, generating, error. Only one heavyweight model context may exist at a time.

### GenerationIntentRouter
Converts conversational requests into a structured generation intent: text2img, img2img, inpaint, outpaint, reference-guided generation, regenerate or edit. The initial implementation should be lightweight and deterministic enough to run alongside the image model on a 4 GB physical-RAM Android target.

### ConversationController
Maintains user requests, assistant status messages, generated images and follow-up relationships so phrases such as “keep everything else the same” can target the previous result.

### ModelPreferences
Persists the default model and load settings. Startup mounts the UI first, then attempts an asynchronous default-model load. A failed load must never lock the prompt UI.

## Low-memory rules

- Target device profile: 4 GB physical RAM.
- Default generation profile: SD1.5-class model, Q4_0, 512x512.
- Never instantiate separate processors for each screen.
- Downscale large reference images before Dart/native RGB expansion.
- Dispose temporary image buffers promptly.
- Serialize generation jobs.
- Changing models must dispose the previous native context before loading the next.

## UI principles

- Neutral charcoal/off-white surfaces instead of saturated blue panels.
- Stable TextEditingController and FocusNode; typing must not trigger route changes or focus loss.
- Prompt composer remains visible at the bottom of the conversation.
- `+` attaches references.
- Generated-image cards expose Edit, Regenerate, Use as Reference and Save.
- Advanced controls are optional.

## Migration rule

Do not keep fixing upstream page-specific navigation/model pickers. Reuse only the generation engine/native bindings that remain useful. FreeFrame owns the app shell and state model from this branch forward.
