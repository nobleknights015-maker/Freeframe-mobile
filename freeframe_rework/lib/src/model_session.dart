import 'dart:async';

enum ModelSessionState { unloaded, loading, ready, generating, error }

class ModelLoadConfig {
  const ModelLoadConfig({
    required this.modelPath,
    this.quantization = 'q4_0',
    this.useTaesd = false,
  });

  final String modelPath;
  final String quantization;
  final bool useTaesd;
}

class GenerationRequest {
  const GenerationRequest({
    required this.prompt,
    this.negativePrompt = '',
    this.width = 512,
    this.height = 512,
    this.seed = -1,
    this.sourceImagePath,
    this.maskImagePath,
  });

  final String prompt;
  final String negativePrompt;
  final int width;
  final int height;
  final int seed;
  final String? sourceImagePath;
  final String? maskImagePath;
}

/// App-level owner for the single native diffusion context.
///
/// The concrete stable-diffusion.cpp bridge will be attached here rather than
/// inside individual screens. Keeping this lifecycle at app scope prevents
/// Text2Img, Img2Img and edit tools from loading duplicate model copies.
class ModelSession {
  ModelSession._();

  static final ModelSession instance = ModelSession._();

  final _stateController = StreamController<ModelSessionState>.broadcast();
  ModelSessionState _state = ModelSessionState.unloaded;
  ModelLoadConfig? _activeConfig;
  String? _lastError;

  Stream<ModelSessionState> get states => _stateController.stream;
  ModelSessionState get state => _state;
  ModelLoadConfig? get activeConfig => _activeConfig;
  String? get lastError => _lastError;
  bool get isReady => _state == ModelSessionState.ready;

  Future<void> load(ModelLoadConfig config) async {
    if (_state == ModelSessionState.loading ||
        _state == ModelSessionState.generating) {
      return;
    }

    _setState(ModelSessionState.loading);
    _lastError = null;

    try {
      // Native bridge hookup lands here. The shell can already depend on this
      // stable lifecycle without owning a processor per page.
      _activeConfig = config;
      _setState(ModelSessionState.ready);
    } catch (error) {
      _lastError = error.toString();
      _setState(ModelSessionState.error);
      rethrow;
    }
  }

  Future<void> generate(GenerationRequest request) async {
    if (!isReady) {
      throw StateError('A model must be loaded before generation.');
    }

    _setState(ModelSessionState.generating);
    _lastError = null;

    try {
      // Native generation dispatch will be serialized here.
      await Future<void>.delayed(Duration.zero);
      _setState(ModelSessionState.ready);
    } catch (error) {
      _lastError = error.toString();
      _setState(ModelSessionState.error);
      rethrow;
    }
  }

  Future<void> unload() async {
    if (_state == ModelSessionState.generating) return;
    _activeConfig = null;
    _lastError = null;
    _setState(ModelSessionState.unloaded);
  }

  void _setState(ModelSessionState next) {
    _state = next;
    _stateController.add(next);
  }

  Future<void> dispose() async {
    await _stateController.close();
  }
}
