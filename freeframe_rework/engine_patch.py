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

# The prompt field must recover cleanly after Android file-picker/model-load
# activity transitions. Force an explicit text-input show after focus is
# requested instead of relying on implicit platform focus restoration.
chat_path = Path('app/lib/src/chat_screen.dart')
chat = chat_path.read_text(encoding='utf-8')

services_import = "import 'package:flutter/services.dart';\n"
if services_import not in chat:
    chat = chat.replace(
        "import 'package:flutter/material.dart';\n",
        "import 'package:flutter/material.dart';\n" + services_import,
        1,
    )

helper_marker = "  Future<void> _restoreModel() async {\n"
if "void _focusPrompt()" not in chat:
    helper = r'''  void _focusPrompt() {
    if (!mounted || _sessionState == ModelSessionState.loading) return;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      _focusNode.requestFocus();
      await SystemChannels.textInput.invokeMethod<void>('TextInput.show');
    });
  }

'''
    if helper_marker not in chat:
        raise SystemExit('FreeFrame chat shape changed: restore marker not found')
    chat = chat.replace(helper_marker, helper + helper_marker, 1)

chat = chat.replace('_focusNode.requestFocus();', '_focusPrompt();')

field_marker = "                        textInputAction: TextInputAction.newline,\n"
if "onTap: _focusPrompt," not in chat:
    if field_marker not in chat:
        raise SystemExit('FreeFrame chat shape changed: text field marker not found')
    chat = chat.replace(
        field_marker,
        "                        textInputAction: TextInputAction.newline,\n                        onTap: _focusPrompt,\n",
        1,
    )

chat_path.write_text(chat, encoding='utf-8')
print('FreeFrame prompt focus patch applied')
