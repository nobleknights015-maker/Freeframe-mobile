from pathlib import Path

path = Path('app/lib/src/chat_screen.dart')
text = path.read_text(encoding='utf-8')

if "import 'cloud_gateway.dart';" not in text:
    text = text.replace(
        "import 'chat_intent.dart';\n",
        "import 'chat_intent.dart';\nimport 'cloud_gateway.dart';\n",
        1,
    )

state_marker = "  bool _restoring = true;\n"
if "bool _cloudMode" not in text:
    if state_marker not in text:
        raise SystemExit('Chat state marker not found')
    text = text.replace(
        state_marker,
        state_marker + "  bool _cloudMode = false;\n  bool _cloudBusy = false;\n",
        1,
    )

old_submit_head = """  Future<void> _submit({String? overrideText}) async {
    final text = (overrideText ?? _controller.text).trim();
    if (text.isEmpty || _sessionState == ModelSessionState.generating) return;

    if (!_session.isReady) {
      _addAssistant(
        'Choose a model first. Tap Models at the top and select your .safetensors, .ckpt, or .gguf file.',
      );
      return;
    }
"""
new_submit_head = """  Future<void> _submit({String? overrideText}) async {
    final text = (overrideText ?? _controller.text).trim();
    if (text.isEmpty || _cloudBusy || _sessionState == ModelSessionState.generating) return;

    if (_cloudMode) {
      await _submitCloud(text);
      return;
    }

    if (!_session.isReady) {
      _addAssistant(
        'Choose a model first. Tap Models at the top and select your .safetensors, .ckpt, or .gguf file.',
      );
      return;
    }
"""
if old_submit_head not in text:
    raise SystemExit('Submit method shape changed')
text = text.replace(old_submit_head, new_submit_head, 1)

cloud_method_marker = "  Future<void> _saveImage(ui.Image image) async {\n"
if "Future<void> _submitCloud(String text)" not in text:
    if cloud_method_marker not in text:
        raise SystemExit('Save image marker not found')
    cloud_method = r'''  Future<void> _submitCloud(String text) async {
    if (!CloudGateway.instance.isConfigured) {
      _addAssistant(
        'Cloud mode is built in, but it is not connected to a FreeFrame cloud server yet. Local mode still works normally.',
      );
      return;
    }

    final attachment = _attachedImage;
    setState(() {
      _items.add(_ChatItem(
        role: _Role.user,
        text: text,
        previewBytes: attachment?.previewBytes,
      ));
      _controller.clear();
      _attachedImage = null;
      _lastPrompt = text;
      _cloudBusy = true;
      _progress = 0;
    });
    _scrollToBottom();

    try {
      final result = await CloudGateway.instance.generate(
        prompt: text,
        referencePng: attachment?.previewBytes,
      );
      final reusable = await ImageInputService.instance.fromGenerated(result.image);
      if (!mounted) return;
      setState(() {
        _lastGeneratedPrepared = reusable;
        _items.add(_ChatItem(
          role: _Role.assistant,
          text: result.generationTime == null
              ? 'Here you go. · Cloud'
              : 'Here you go. · Cloud · ${result.generationTime}',
          generatedImage: result.image,
        ));
      });
      _scrollToBottom();
    } catch (error) {
      if (mounted) {
        _addAssistant('Cloud generation stopped: ${_friendlyError(error)}');
      }
    } finally {
      if (mounted) {
        setState(() => _cloudBusy = false);
        _focusPrompt();
      }
    }
  }

'''
    text = text.replace(cloud_method_marker, cloud_method + cloud_method_marker, 1)

status_marker = "  String get _statusText {\n"
if "Cloud · Ready" not in text:
    status_inject = """  String get _statusText {
    if (_cloudMode) {
      if (_cloudBusy) return 'Cloud · Generating…';
      return CloudGateway.instance.isConfigured
          ? 'Cloud · Ready'
          : 'Cloud · Not connected';
    }
"""
    if status_marker not in text:
        raise SystemExit('Status marker not found')
    text = text.replace(status_marker, status_inject, 1)

busy_old = """    final busy = _sessionState == ModelSessionState.loading ||
        _sessionState == ModelSessionState.generating;
"""
busy_new = """    final busy = _cloudBusy ||
        _sessionState == ModelSessionState.loading ||
        _sessionState == ModelSessionState.generating;
"""
if busy_old not in text:
    raise SystemExit('Busy marker not found')
text = text.replace(busy_old, busy_new, 1)

models_action = """          TextButton.icon(
            onPressed: busy ? null : _chooseModel,
            icon: const Icon(Icons.tune_rounded, size: 19),
            label: const Text('Models'),
          ),
          const SizedBox(width: 6),
"""
if models_action not in text:
    # Source before engine patch still points at _openModelsPanel. Support both.
    models_action = models_action.replace('_chooseModel', '_openModelsPanel')
if models_action not in text:
    raise SystemExit('Models action marker not found')

hybrid_action = """          SegmentedButton<bool>(
            segments: const [
              ButtonSegment<bool>(
                value: false,
                icon: Icon(Icons.smartphone_rounded, size: 17),
                label: Text('Local'),
              ),
              ButtonSegment<bool>(
                value: true,
                icon: Icon(Icons.cloud_rounded, size: 17),
                label: Text('Cloud'),
              ),
            ],
            selected: {_cloudMode},
            showSelectedIcon: false,
            onSelectionChanged: busy
                ? null
                : (value) {
                    setState(() => _cloudMode = value.first);
                  },
          ),
          const SizedBox(width: 6),
""" + models_action
text = text.replace(models_action, hybrid_action, 1)

progress_old = """            if (_sessionState == ModelSessionState.generating)
              LinearProgressIndicator(value: _progress > 0 ? _progress : null),
"""
progress_new = """            if (_cloudBusy || _sessionState == ModelSessionState.generating)
              LinearProgressIndicator(
                value: _cloudMode ? null : (_progress > 0 ? _progress : null),
              ),
"""
if progress_old not in text:
    raise SystemExit('Progress marker not found')
text = text.replace(progress_old, progress_new, 1)

path.write_text(text, encoding='utf-8')
print('FreeFrame Local/Cloud hybrid mode applied')
