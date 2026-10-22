import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class SavedModelSettings {
  const SavedModelSettings({
    required this.modelPath,
    this.quantization = 'q4_0',
    this.useTaesd = false,
    this.autoLoad = true,
  });

  final String modelPath;
  final String quantization;
  final bool useTaesd;
  final bool autoLoad;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'modelPath': modelPath,
        'quantization': quantization,
        'useTaesd': useTaesd,
        'autoLoad': autoLoad,
      };

  static SavedModelSettings? fromJson(Map<String, dynamic> json) {
    final path = json['modelPath'] as String?;
    if (path == null || path.trim().isEmpty) return null;
    return SavedModelSettings(
      modelPath: path,
      quantization: (json['quantization'] as String?) ?? 'q4_0',
      useTaesd: (json['useTaesd'] as bool?) ?? false,
      autoLoad: (json['autoLoad'] as bool?) ?? true,
    );
  }
}

class SettingsStore {
  SettingsStore._();

  static final SettingsStore instance = SettingsStore._();

  Future<File> _file() async {
    final dir = await getApplicationSupportDirectory();
    final configDir = Directory('${dir.path}/freeframe');
    if (!await configDir.exists()) {
      await configDir.create(recursive: true);
    }
    return File('${configDir.path}/settings.json');
  }

  Future<SavedModelSettings?> readDefaultModel() async {
    try {
      final file = await _file();
      if (!await file.exists()) return null;
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is! Map<String, dynamic>) return null;
      return SavedModelSettings.fromJson(decoded);
    } catch (_) {
      return null;
    }
  }

  Future<void> saveDefaultModel(SavedModelSettings settings) async {
    final file = await _file();
    await file.writeAsString(jsonEncode(settings.toJson()), flush: true);
  }

  Future<void> clearDefaultModel() async {
    final file = await _file();
    if (await file.exists()) await file.delete();
  }
}
