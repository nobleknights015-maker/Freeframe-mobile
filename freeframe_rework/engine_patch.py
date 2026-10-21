from pathlib import Path

path = Path('app/lib/img2img_processor.dart')
text = path.read_text(encoding='utf-8')

case_marker = "          case 'img2img':\n"
if case_marker not in text:
    raise SystemExit('Pinned Img2Img processor shape changed: img2img case not found')

if "case 'freeframeTxt2Img':" not in text:
    txt2img_case = r'''          case 'freeframeTxt2Img':
            _lastGenerationTime = null;
            _collectedLogs.clear();
            if (ctx == null || ctx!.address == 0) {
              mainSendPort.send({
                'type': 'error',
                'errorType': 'generationError',
                'message': 'Model not initialized in isolate'
              });
              break;
            }

            Pointer<Utf8>? promptUtf8;
            Pointer<Utf8>? negPromptUtf8;
            Pointer<Utf8>? emptyUtf8;
            try {
              promptUtf8 = message['prompt'].toString().toNativeUtf8();
              negPromptUtf8 = message['negativePrompt'].toString().toNativeUtf8();
              emptyUtf8 = ''.toNativeUtf8();

              final result = FFIBindings.txt2img(
                ctx!,
                promptUtf8,
                negPromptUtf8,
                message['clipSkip'],
                message['cfgScale'],
                message['guidance'],
                message['eta'],
                message['width'],
                message['height'],
                message['sampleMethod'],
                message['sampleSteps'],
                message['seed'],
                1,
                nullptr,
                0.0,
                1.0,
                false,
                emptyUtf8,
                nullptr,
                0,
                0.0,
                0.01,
                0.2,
              );

              if (result.address == 0) {
                mainSendPort.send({
                  'type': 'error',
                  'errorType': 'generationError',
                  'message': 'Text-to-image generation failed'
                });
                break;
              }

              final image = result.cast<SDImage>().ref;
              final pixelCount = image.width * image.height;
              final bytes = image.data.asTypedList(pixelCount * image.channel);
              final rgbaBytes = Uint8List(pixelCount * 4);
              for (var i = 0; i < pixelCount; i++) {
                rgbaBytes[i * 4] = bytes[i * image.channel];
                rgbaBytes[i * 4 + 1] = bytes[i * image.channel + 1];
                rgbaBytes[i * 4 + 2] = bytes[i * image.channel + 2];
                rgbaBytes[i * 4 + 3] = 255;
              }
              mainSendPort.send({
                'type': 'image',
                'bytes': rgbaBytes,
                'width': image.width,
                'height': image.height,
                'generationTime': _lastGenerationTime,
              });
              calloc.free(image.data);
              calloc.free(result.cast<Void>());
            } catch (e) {
              mainSendPort.send({
                'type': 'error',
                'errorType': 'generationError',
                'message': 'Generation error: ${e.toString()}'
              });
            } finally {
              if (promptUtf8 != null) calloc.free(promptUtf8);
              if (negPromptUtf8 != null) calloc.free(negPromptUtf8);
              if (emptyUtf8 != null) calloc.free(emptyUtf8);
              mainSendPort.send({'type': 'logs', 'logs': _collectedLogs});
            }
            break;

'''
    text = text.replace(case_marker, txt2img_case + case_marker, 1)

method_marker = "  Future<void> generateImg2Img({\n"
if method_marker not in text:
    raise SystemExit('Pinned Img2Img processor shape changed: generateImg2Img not found')

if "Future<void> generateTextToImage({" not in text:
    method = r'''  Future<void> generateTextToImage({
    required String prompt,
    String negativePrompt = '',
    int clipSkip = 1,
    double cfgScale = 7.0,
    double guidance = 1.0,
    double eta = 0.0,
    int width = 512,
    int height = 512,
    int sampleMethod = 0,
    int sampleSteps = 20,
    int seed = -1,
  }) async {
    await _uninitialized.future;
    _sdSendPort.send({
      'command': 'freeframeTxt2Img',
      'prompt': prompt,
      'negativePrompt': negativePrompt,
      'clipSkip': clipSkip,
      'cfgScale': cfgScale,
      'guidance': guidance,
      'eta': eta,
      'width': width,
      'height': height,
      'sampleMethod': sampleMethod,
      'sampleSteps': sampleSteps,
      'seed': seed,
    });
  }

'''
    text = text.replace(method_marker, method + method_marker, 1)

path.write_text(text, encoding='utf-8')
print('FreeFrame shared native processor patch applied')

# Harden the prompt keyboard and external picker lifecycle for low-memory Android.
chat_path = Path('app/lib/src/chat_screen.dart')
chat = chat_path.read_text(encoding='utf-8')

services_import = "import 'package:flutter/services.dart';\n"
if services_import not in chat:
    chat = chat.replace(
        "import 'package:flutter/material.dart';\n",
        "import 'package:flutter/material.dart';\n" + services_import,
        1,
    )

# Replace existing direct focus requests before inserting the helper so the
# helper itself can safely call requestFocus without being rewritten.
if "void _focusPrompt()" not in chat:
    chat = chat.replace('_focusNode.requestFocus();', '_focusPrompt();')
    helper_marker = "  Future<void> _restoreModel() async {\n"
    helper = r'''  void _focusPrompt() {
    if (!mounted) return;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      if (!_focusNode.hasFocus) {
        FocusScope.of(context).requestFocus(_focusNode);
      }
      await Future<void>.delayed(const Duration(milliseconds: 120));
      if (!mounted || !_focusNode.hasFocus) return;
      await SystemChannels.textInput.invokeMethod<void>('TextInput.show');
    });
  }

'''
    if helper_marker not in chat:
        raise SystemExit('FreeFrame chat shape changed: restore marker not found')
    chat = chat.replace(helper_marker, helper + helper_marker, 1)

# Keep the text input connection alive while the model is loading. Disabling
# and re-enabling TextField on this Motorola target was leaving the IME in a
# broken state after the native model transition.
chat = chat.replace(
    "                        enabled: _sessionState != ModelSessionState.loading,\n",
    "",
    1,
)

field_marker = "                        textInputAction: TextInputAction.newline,\n"
if "onTap: _focusPrompt," not in chat:
    if field_marker not in chat:
        raise SystemExit('FreeFrame chat shape changed: text field marker not found')
    chat = chat.replace(
        field_marker,
        "                        textInputAction: TextInputAction.newline,\n                        onTap: _focusPrompt,\n",
        1,
    )

# A multi-gigabyte model remaining resident while Android opens DocumentsUI can
# cause the 4 GB target phone to kill FreeFrame in the background. Release the
# native model context before leaving the app, then restore the same model after
# the picker returns. The persisted default is left unchanged.
old_picker = r'''  Future<void> _pickReference() async {
    try {
      final prepared = await ImageInputService.instance.pickReference();
      if (prepared == null || !mounted) return;
      setState(() => _attachedImage = prepared);
      _focusPrompt();
    } catch (error) {
      if (mounted) {
        _addAssistant('I could not open that image. ${_friendlyError(error)}');
      }
    }
  }
'''

new_picker = r'''  Future<void> _pickReference() async {
    final config = _session.activeConfig;
    final shouldRestoreModel = config != null && _session.isReady;
    try {
      _focusNode.unfocus();
      await SystemChannels.textInput.invokeMethod<void>('TextInput.hide');

      if (shouldRestoreModel) {
        await _session.unload();
        await Future<void>.delayed(const Duration(milliseconds: 250));
      }

      final prepared = await ImageInputService.instance.pickReference();
      if (prepared != null && mounted) {
        setState(() => _attachedImage = prepared);
      }
    } catch (error) {
      if (mounted) {
        _addAssistant('I could not open that image. ${_friendlyError(error)}');
      }
    } finally {
      if (shouldRestoreModel && config != null && mounted) {
        try {
          await _session.load(config, persist: false);
        } catch (error) {
          if (mounted) {
            _addAssistant(
              'The image picker returned, but I could not reload the model. ${_friendlyError(error)}',
            );
          }
        }
      }
      if (mounted) _focusPrompt();
    }
  }
'''

if old_picker not in chat:
    raise SystemExit('FreeFrame chat shape changed: reference picker method not found')
chat = chat.replace(old_picker, new_picker, 1)

# Moto G safe-generation profile. Keep the known-good Q4 model quality while
# lowering the short-lived allocation spike that was killing the process at
# sampling start on the physical 4 GB device.
chat = chat.replace('        width: source?.width ?? 512,\n', '        width: 448,\n', 1)
chat = chat.replace('        height: source?.height ?? 512,\n', '        height: 448,\n', 1)
strength_marker = "        strength: intent.action == FreeFrameAction.editImage ? 0.45 : 0.58,\n"
if "        steps: 15,\n" not in chat:
    if strength_marker not in chat:
        raise SystemExit('FreeFrame chat shape changed: generation request marker not found')
    chat = chat.replace(strength_marker, "        steps: 15,\n" + strength_marker, 1)

# Purge Flutter's decoded-image cache immediately before native sampling. This
# does not touch the selected model or source RGB data needed by the request.
generate_marker = "    try {\n      final result = await _session.generate(GenerationRequest(\n"
if "imageCache.clearLiveImages" not in chat:
    if generate_marker not in chat:
        raise SystemExit('FreeFrame chat shape changed: generate marker not found')
    chat = chat.replace(
        generate_marker,
        "    try {\n      PaintingBinding.instance.imageCache.clear();\n      PaintingBinding.instance.imageCache.clearLiveImages();\n      await Future<void>.delayed(const Duration(milliseconds: 80));\n      final result = await _session.generate(GenerationRequest(\n",
        1,
    )

chat_path.write_text(chat, encoding='utf-8')
print('FreeFrame keyboard, picker, and low-memory generation hardening applied')

# Apply the same safe defaults at the session layer so any future generation
# entry point gets the low-memory profile even if it does not come from chat.
session_path = Path('app/lib/src/model_session.dart')
session = session_path.read_text(encoding='utf-8')
session = session.replace('    this.width = 512,\n', '    this.width = 448,\n', 1)
session = session.replace('    this.height = 512,\n', '    this.height = 448,\n', 1)
session = session.replace('    this.steps = 20,\n', '    this.steps = 15,\n', 1)
session = session.replace('        useFlashAttention: false,\n', '        useFlashAttention: true,\n', 1)
session_path.write_text(session, encoding='utf-8')
print('FreeFrame Moto G safe session defaults applied')
