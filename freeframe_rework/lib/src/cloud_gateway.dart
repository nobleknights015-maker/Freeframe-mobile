import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

class CloudGenerationResult {
  const CloudGenerationResult({
    required this.image,
    this.generationTime,
  });

  final ui.Image image;
  final String? generationTime;
}

/// Thin FreeFrame client for a server-side image-generation gateway.
///
/// The OpenAI API key must NEVER be stored in the APK. The app talks only to
/// FREEFRAME_CLOUD_URL, and that trusted server keeps the provider credential.
class CloudGateway {
  CloudGateway._();

  static final CloudGateway instance = CloudGateway._();

  static const endpoint = String.fromEnvironment('FREEFRAME_CLOUD_URL');

  bool get isConfigured => endpoint.trim().isNotEmpty;

  Future<CloudGenerationResult> generate({
    required String prompt,
    Uint8List? referencePng,
  }) async {
    if (!isConfigured) {
      throw StateError(
        'Cloud mode is not connected yet. This build needs a FreeFrame cloud gateway URL.',
      );
    }

    final client = HttpClient();
    client.connectionTimeout = const Duration(seconds: 20);
    try {
      final request = await client.postUrl(Uri.parse(endpoint));
      request.headers.contentType = ContentType.json;
      request.write(jsonEncode({
        'prompt': prompt,
        if (referencePng != null)
          'reference_image_base64': base64Encode(referencePng),
      }));

      final response = await request.close().timeout(const Duration(minutes: 3));
      final body = await utf8.decoder.bind(response).join();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw StateError('Cloud generation failed (${response.statusCode}). $body');
      }

      final decoded = jsonDecode(body);
      if (decoded is! Map<String, dynamic>) {
        throw StateError('Cloud gateway returned an invalid response.');
      }
      final encoded = decoded['image_base64'];
      if (encoded is! String || encoded.isEmpty) {
        throw StateError('Cloud gateway returned no image.');
      }

      final png = base64Decode(encoded);
      final codec = await ui.instantiateImageCodec(png);
      try {
        final frame = await codec.getNextFrame();
        return CloudGenerationResult(
          image: frame.image,
          generationTime: decoded['generation_time'] as String?,
        );
      } finally {
        codec.dispose();
      }
    } finally {
      client.close(force: true);
    }
  }
}
