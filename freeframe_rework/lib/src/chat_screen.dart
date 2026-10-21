import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:gal/gal.dart';

import 'chat_intent.dart';
import 'image_input.dart';
import 'model_session.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();
  final _scrollController = ScrollController();
  final _session = ModelSession.instance;
  final _parser = const ChatIntentParser();

  final List<_ChatItem> _items = <_ChatItem>[
    const _ChatItem(
      role: _Role.assistant,
      text: 'What would you like to create?',
    ),
  ];

  StreamSubscription<ModelSessionState>? _stateSub;
  StreamSubscription<double>? _progressSub;
  ModelSessionState _sessionState = ModelSessionState.unloaded;
  double _progress = 0;
  PreparedImage? _attachedImage;
  PreparedImage? _lastGeneratedPrepared;
  String? _lastPrompt;
  bool _restoring = true;

  @override
  void initState() {
    super.initState();
    _sessionState = _session.state;
    _stateSub = _session.states.listen((state) {
      if (!mounted) return;
      setState(() => _sessionState = state);
    });
    _progressSub = _session.progress.listen((value) {
      if (!mounted) return;
      setState(() => _progress = value);
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _restoreModel());
  }

  Future<void> _restoreModel() async {
    try {
      final restored = await _session.restoreDefaultModel();
      if (restored && mounted) {
        _addAssistant('Default model loaded. Ready when you are.');
      }
    } catch (error) {
      if (mounted) {
        _addAssistant('I remembered your model, but it could not be loaded. Choose it again from Models.');
      }
    } finally {
      if (mounted) setState(() => _restoring = false);
    }
  }

  @override
  void dispose() {
    _stateSub?.cancel();
    _progressSub?.cancel();
    _controller.dispose();
    _focusNode.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _chooseModel() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['safetensors', 'ckpt', 'gguf'],
      allowMultiple: false,
    );
    final path = result?.files.single.path;
    if (path == null) return;

    _addAssistant('Loading ${_fileName(path)}…');
    try {
      await _session.load(ModelLoadConfig(modelPath: path));
      if (!mounted) return;
      _addAssistant('${_fileName(path)} is loaded and set as your default model.');
    } catch (error) {
      if (!mounted) return;
      _addAssistant('That model could not be loaded. ${_friendlyError(error)}');
    }
  }

  Future<void> _pickReference() async {
    try {
      final prepared = await ImageInputService.instance.pickReference();
      if (prepared == null || !mounted) return;
      setState(() => _attachedImage = prepared);
      _focusNode.requestFocus();
    } catch (error) {
      if (mounted) _addAssistant('I could not open that image. ${_friendlyError(error)}');
    }
  }

  Future<void> _submit({String? overrideText}) async {
    final text = (overrideText ?? _controller.text).trim();
    if (text.isEmpty || _sessionState == ModelSessionState.generating) return;

    if (!_session.isReady) {
      _addAssistant('Choose a model first. Tap Models at the top and select your .safetensors, .ckpt, or .gguf file.');
      return;
    }

    final attachment = _attachedImage;
    final previous = _lastGeneratedPrepared;
    final intent = _parser.parse(
      text: text,
      hasAttachedImage: attachment != null,
      hasPreviousImage: previous != null,
    );

    PreparedImage? source;
    if (intent.action == FreeFrameAction.imageToImage ||
        intent.action == FreeFrameAction.editImage) {
      source = attachment ?? previous;
    } else if (intent.action == FreeFrameAction.reuseReference) {
      source = previous;
    }

    setState(() {
      _items.add(_ChatItem(
        role: _Role.user,
        text: text,
        previewBytes: attachment?.previewBytes,
      ));
      _controller.clear();
      _attachedImage = null;
      _lastPrompt = text;
      _progress = 0;
    });
    _scrollToBottom();

    try {
      final result = await _session.generate(GenerationRequest(
        prompt: intent.prompt,
        width: source?.width ?? 512,
        height: source?.height ?? 512,
        inputImageData: source?.rgb,
        inputWidth: source?.width,
        inputHeight: source?.height,
        strength: intent.action == FreeFrameAction.editImage ? 0.45 : 0.58,
      ));

      final reusable = await ImageInputService.instance.fromGenerated(result.image);
      if (!mounted) return;
      setState(() {
        _lastGeneratedPrepared = reusable;
        _items.add(_ChatItem(
          role: _Role.assistant,
          text: result.generationTime == null
              ? 'Here you go.'
              : 'Here you go. Generated in ${result.generationTime}.',
          generatedImage: result.image,
        ));
      });
      _scrollToBottom();
    } catch (error) {
      if (!mounted) return;
      _addAssistant('Generation stopped: ${_friendlyError(error)}');
    } finally {
      if (mounted) _focusNode.requestFocus();
    }
  }

  Future<void> _saveImage(ui.Image image) async {
    try {
      final data = await image.toByteData(format: ui.ImageByteFormat.png);
      if (data == null) throw StateError('Could not encode image.');
      final bytes = data.buffer.asUint8List();
      await Gal.putImageBytes(
        bytes,
        name: 'FreeFrame_${DateTime.now().millisecondsSinceEpoch}.png',
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Saved to your gallery.')),
        );
      }
    } catch (error) {
      if (mounted) _addAssistant('I could not save that image. ${_friendlyError(error)}');
    }
  }

  Future<void> _useGeneratedAsReference(ui.Image image) async {
    try {
      final prepared = await ImageInputService.instance.fromGenerated(image);
      if (!mounted) return;
      setState(() => _attachedImage = prepared);
      _focusNode.requestFocus();
    } catch (error) {
      if (mounted) _addAssistant('I could not reuse that image. ${_friendlyError(error)}');
    }
  }

  void _addAssistant(String text) {
    if (!mounted) return;
    setState(() => _items.add(_ChatItem(role: _Role.assistant, text: text)));
    _scrollToBottom();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
      );
    });
  }

  String _fileName(String path) => path.split(RegExp(r'[/\\]')).last;

  String _friendlyError(Object error) {
    return error.toString().replaceFirst('Bad state: ', '').replaceFirst('StateError: ', '');
  }

  String get _statusText {
    if (_restoring) return 'Checking default model…';
    switch (_sessionState) {
      case ModelSessionState.unloaded:
        return 'No model loaded';
      case ModelSessionState.loading:
        return 'Loading model…';
      case ModelSessionState.ready:
        return _session.activeConfig == null
            ? 'Ready'
            : 'Ready · ${_fileName(_session.activeConfig!.modelPath)}';
      case ModelSessionState.generating:
        return 'Generating ${(_progress * 100).round()}%';
      case ModelSessionState.error:
        return 'Needs attention';
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final busy = _sessionState == ModelSessionState.loading ||
        _sessionState == ModelSessionState.generating;

    return Scaffold(
      appBar: AppBar(
        title: const Text('FreeFrame'),
        centerTitle: false,
        backgroundColor: Colors.transparent,
        scrolledUnderElevation: 0,
        actions: [
          TextButton.icon(
            onPressed: busy ? null : _chooseModel,
            icon: const Icon(Icons.tune_rounded, size: 19),
            label: const Text('Models'),
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
              child: Align(
                alignment: Alignment.centerLeft,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: scheme.surfaceContainer,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: scheme.outlineVariant),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    child: Text(_statusText, style: Theme.of(context).textTheme.labelMedium),
                  ),
                ),
              ),
            ),
            if (_sessionState == ModelSessionState.generating)
              LinearProgressIndicator(value: _progress > 0 ? _progress : null),
            Expanded(
              child: ListView.builder(
                controller: _scrollController,
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
                itemCount: _items.length,
                itemBuilder: (context, index) {
                  final item = _items[index];
                  final isUser = item.role == _Role.user;
                  return Align(
                    alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                    child: Container(
                      constraints: const BoxConstraints(maxWidth: 640),
                      margin: const EdgeInsets.symmetric(vertical: 6),
                      padding: EdgeInsets.all(item.generatedImage == null ? 12 : 8),
                      decoration: BoxDecoration(
                        color: isUser ? scheme.surfaceContainerHighest : Colors.transparent,
                        borderRadius: BorderRadius.circular(18),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (item.previewBytes != null) ...[
                            ClipRRect(
                              borderRadius: BorderRadius.circular(12),
                              child: Image.memory(
                                item.previewBytes!,
                                width: 170,
                                fit: BoxFit.cover,
                              ),
                            ),
                            const SizedBox(height: 8),
                          ],
                          if (item.generatedImage != null) ...[
                            ClipRRect(
                              borderRadius: BorderRadius.circular(14),
                              child: RawImage(
                                image: item.generatedImage,
                                fit: BoxFit.contain,
                              ),
                            ),
                            const SizedBox(height: 8),
                          ],
                          if (item.text.isNotEmpty)
                            Text(item.text, style: Theme.of(context).textTheme.bodyLarge),
                          if (item.generatedImage != null) ...[
                            const SizedBox(height: 4),
                            Wrap(
                              spacing: 6,
                              children: [
                                TextButton.icon(
                                  onPressed: () => _useGeneratedAsReference(item.generatedImage!),
                                  icon: const Icon(Icons.edit_rounded, size: 18),
                                  label: const Text('Edit'),
                                ),
                                TextButton.icon(
                                  onPressed: () => _useGeneratedAsReference(item.generatedImage!),
                                  icon: const Icon(Icons.link_rounded, size: 18),
                                  label: const Text('Use as reference'),
                                ),
                                TextButton.icon(
                                  onPressed: _lastPrompt == null ? null : () => _submit(overrideText: _lastPrompt),
                                  icon: const Icon(Icons.refresh_rounded, size: 18),
                                  label: const Text('Retry'),
                                ),
                                TextButton.icon(
                                  onPressed: () => _saveImage(item.generatedImage!),
                                  icon: const Icon(Icons.download_rounded, size: 18),
                                  label: const Text('Save'),
                                ),
                              ],
                            ),
                          ],
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            if (_attachedImage != null)
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 0, 14, 6),
                child: Row(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: Image.memory(
                        _attachedImage!.previewBytes!,
                        width: 64,
                        height: 64,
                        fit: BoxFit.cover,
                      ),
                    ),
                    const SizedBox(width: 10),
                    const Expanded(child: Text('Reference attached')),
                    IconButton(
                      tooltip: 'Remove reference',
                      onPressed: () => setState(() => _attachedImage = null),
                      icon: const Icon(Icons.close_rounded),
                    ),
                  ],
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 6, 12, 12),
              child: Container(
                decoration: BoxDecoration(
                  color: scheme.surfaceContainer,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: scheme.outlineVariant),
                ),
                padding: const EdgeInsets.all(6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    IconButton(
                      tooltip: 'Attach reference',
                      onPressed: busy ? null : _pickReference,
                      icon: const Icon(Icons.add_rounded),
                    ),
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        focusNode: _focusNode,
                        enabled: _sessionState != ModelSessionState.loading,
                        minLines: 1,
                        maxLines: 6,
                        textInputAction: TextInputAction.newline,
                        decoration: const InputDecoration(
                          hintText: 'Describe what you want…',
                          border: InputBorder.none,
                          contentPadding: EdgeInsets.symmetric(vertical: 12),
                        ),
                      ),
                    ),
                    IconButton.filled(
                      tooltip: 'Generate',
                      onPressed: busy ? null : _submit,
                      icon: _sessionState == ModelSessionState.generating
                          ? const SizedBox.square(
                              dimension: 18,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.arrow_upward_rounded),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

enum _Role { user, assistant }

class _ChatItem {
  const _ChatItem({
    required this.role,
    required this.text,
    this.previewBytes,
    this.generatedImage,
  });

  final _Role role;
  final String text;
  final Uint8List? previewBytes;
  final ui.Image? generatedImage;
}
