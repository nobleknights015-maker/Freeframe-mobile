import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import '../ffi_bindings.dart';
import '../img2img_processor.dart';
import 'settings_store.dart';

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
    this.steps = 20,
    this.cfgScale = 7.0,
    this.strength = 0.55,
    this.inputImageData,
    this.inputWidth,
    this.inputHeight,
    this.inputChannels = 3,
    this.maskImageData,
  });

  final String prompt;
  final String negativePrompt;
  final int width;
  final int height;
  final int seed;
  final int steps;
  final double cfgScale;
  final double strength;
  final Uint8List? inputImageData;
  final int? inputWidth;
  final int? inputHeight;
  final int inputChannels;
  final Uint8List? maskImageData;

  bool get usesSourceImage => inputImageData != null;
}

class GenerationResult {
  const GenerationResult({
    required this.image,
    this.generationTime,
  });

  final ui.Image image;
  final String? generationTime;
}

/// Owns exactly one native stable-diffusion.cpp context for the whole app.
///
/// FreeFrame patches the pinned upstream Img2Img processor so its single worker
/// isolate can dispatch both txt2img and img2img against the same loaded ctx.
/// This is the core low-memory rule for the 4 GB target device.
class ModelSession {
  ModelSession._();

  static final ModelSession instance = ModelSession._();

  final _stateController = StreamController<ModelSessionState>.broadcast();
  final _resultController = StreamController<GenerationResult>.broadcast();
  final _progressController = StreamController<double>.broadcast();

  ModelSessionState _state = ModelSessionState.unloaded;
  ModelLoadConfig? _activeConfig;
  String? _lastError;
  Img2ImgProcessor? _processor;
  StreamSubscription<Map<String, dynamic>>? _resultSubscription;
  Completer<void>? _loadCompleter;
  Completer<GenerationResult>? _generationCompleter;

  Stream<ModelSessionState> get states => _stateController.stream;
  Stream<GenerationResult> get results => _resultController.stream;
  Stream<double> get progress => _progressController.stream;
  ModelSessionState get state => _state;
  ModelLoadConfig? get activeConfig => _activeConfig;
  String? get lastError => _lastError;
  bool get isReady => _state == ModelSessionState.ready;

  Future<bool> restoreDefaultModel() async {
    final saved = await SettingsStore.instance.readDefaultModel();
    if (saved == null || !saved.autoLoad) return false;
    if (!await File(saved.modelPath).exists()) {
      _lastError = 'The saved default model could not be found.';
      _setState(ModelSessionState.error);
      return false;
    }
    await load(ModelLoadConfig(
      modelPath: saved.modelPath,
      quantization: saved.quantization,
      useTaesd: saved.useTaesd,
    ));
    return true;
  }

  Future<void> load(ModelLoadConfig config, {bool persist = true}) async {
    if (_state == ModelSessionState.loading ||
        _state == ModelSessionState.generating) {
      return;
    }

    if (_activeConfig?.modelPath == config.modelPath && isReady) return;

    if (!await File(config.modelPath).exists()) {
      throw StateError('Model file not found: ${config.modelPath}');
    }

    await unload();
    _setState(ModelSessionState.loading);
    _lastError = null;
    final completer = Completer<void>();
    _loadCompleter = completer;

    try {
      final processor = Img2ImgProcessor(
        modelPath: config.modelPath,
        useFlashAttention: false,
        modelType: _modelType(config.quantization),
        schedule: Schedule.DISCRETE,
        useTinyAutoencoder: config.useTaesd,
        isDiffusionModelType: false,
        onModelLoaded: () {
          if (!completer.isCompleted) completer.complete();
        },
        onLog: (message) {
          if (message.level < 0 && !completer.isCompleted) {
            completer.completeError(StateError(message.message));
          }
        },
        onProgress: (update) {
          _progressController.add(update.progress.clamp(0.0, 1.0));
        },
      );

      _processor = processor;
      _resultSubscription = processor.generationResultStream.listen((payload) {
        final image = payload['image'];
        if (image is! ui.Image) return;
        final result = GenerationResult(
          image: image,
          generationTime: payload['generationTime'] as String?,
        );
        _resultController.add(result);
        final pending = _generationCompleter;
        if (pending != null && !pending.isCompleted) pending.complete(result);
      });

      await completer.future.timeout(
        const Duration(minutes: 8),
        onTimeout: () => throw TimeoutException('Model loading timed out.'),
      );

      _activeConfig = config;
      _setState(ModelSessionState.ready);
      if (persist) {
        await SettingsStore.instance.saveDefaultModel(SavedModelSettings(
          modelPath: config.modelPath,
          quantization: config.quantization,
          useTaesd: config.useTaesd,
          autoLoad: true,
        ));
      }
    } catch (error) {
      _lastError = error.toString();
      _setState(ModelSessionState.error);
      _processor?.dispose();
      _processor = null;
      await _resultSubscription?.cancel();
      _resultSubscription = null;
      rethrow;
    } finally {
      _loadCompleter = null;
    }
  }

  Future<GenerationResult> generate(GenerationRequest request) async {
    final processor = _processor;
    if (processor == null || !isReady) {
      throw StateError('Choose a model before generating.');
    }
    if (_generationCompleter != null && !_generationCompleter!.isCompleted) {
      throw StateError('A generation is already running.');
    }

    _setState(ModelSessionState.generating);
    _lastError = null;
    _progressController.add(0);
    final completer = Completer<GenerationResult>();
    _generationCompleter = completer;

    try {
      if (request.usesSourceImage) {
        final inputWidth = request.inputWidth;
        final inputHeight = request.inputHeight;
        if (inputWidth == null || inputHeight == null) {
          throw ArgumentError('Source image dimensions are required.');
        }
        await processor.generateImg2Img(
          inputImageData: request.inputImageData!,
          inputWidth: inputWidth,
          inputHeight: inputHeight,
          channel: request.inputChannels,
          outputWidth: request.width,
          outputHeight: request.height,
          prompt: request.prompt,
          negativePrompt: request.negativePrompt,
          cfgScale: request.cfgScale,
          guidance: 1.0,
          sampleMethod: 0,
          sampleSteps: request.steps,
          strength: request.strength,
          seed: request.seed,
          maskImageData: request.maskImageData,
          maskWidth: request.maskImageData == null ? null : request.width,
          maskHeight: request.maskImageData == null ? null : request.height,
        );
      } else {
        await processor.generateTextToImage(
          prompt: request.prompt,
          negativePrompt: request.negativePrompt,
          cfgScale: request.cfgScale,
          guidance: 1.0,
          width: request.width,
          height: request.height,
          sampleSteps: request.steps,
          seed: request.seed,
        );
      }

      final result = await completer.future.timeout(
        const Duration(minutes: 15),
        onTimeout: () => throw TimeoutException('Generation timed out.'),
      );
      _progressController.add(1);
      _setState(ModelSessionState.ready);
      return result;
    } catch (error) {
      _lastError = error.toString();
      _setState(ModelSessionState.error);
      rethrow;
    } finally {
      _generationCompleter = null;
    }
  }

  Future<void> unload() async {
    if (_state == ModelSessionState.generating) return;
    await _resultSubscription?.cancel();
    _resultSubscription = null;
    _processor?.dispose();
    _processor = null;
    _activeConfig = null;
    _lastError = null;
    if (_state != ModelSessionState.unloaded) {
      _setState(ModelSessionState.unloaded);
    }
  }

  SDType _modelType(String value) {
    switch (value.toLowerCase()) {
      case 'q8_0':
        return SDType.SD_TYPE_Q8_0;
      case 'q6_k':
        return SDType.SD_TYPE_Q6_K;
      case 'q5_0':
        return SDType.SD_TYPE_Q5_0;
      case 'q5_1':
        return SDType.SD_TYPE_Q5_1;
      case 'q5_k':
        return SDType.SD_TYPE_Q5_K;
      case 'q4_1':
        return SDType.SD_TYPE_Q4_1;
      case 'q4_k':
        return SDType.SD_TYPE_Q4_K;
      case 'q3_k':
        return SDType.SD_TYPE_Q3_K;
      case 'q2_k':
        return SDType.SD_TYPE_Q2_K;
      case 'q4_0':
      default:
        return SDType.SD_TYPE_Q4_0;
    }
  }

  void _setState(ModelSessionState next) {
    _state = next;
    if (!_stateController.isClosed) _stateController.add(next);
  }

  Future<void> dispose() async {
    await unload();
    await _stateController.close();
    await _resultController.close();
    await _progressController.close();
  }
}
