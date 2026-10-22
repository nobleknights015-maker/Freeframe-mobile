import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:file_picker/file_picker.dart';

class PreparedImage {
  const PreparedImage({
    required this.rgb,
    required this.width,
    required this.height,
    this.previewBytes,
    this.sourcePath,
  });

  final Uint8List rgb;
  final int width;
  final int height;
  final Uint8List? previewBytes;
  final String? sourcePath;
}

class ImageInputService {
  ImageInputService._();

  static final ImageInputService instance = ImageInputService._();

  /// Uses the Android document picker instead of image_picker.
  ///
  /// This avoids decoding a full camera-resolution bitmap in the picker
  /// activity while a multi-GB diffusion model is already resident in RAM.
  Future<PreparedImage?> pickReference() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.image,
      allowMultiple: false,
      withData: false,
    );
    final path = result?.files.single.path;
    if (path == null) return null;

    final file = File(path);
    if (!await file.exists()) {
      throw StateError('The selected image is no longer available.');
    }

    final bytes = await file.readAsBytes();
    return _prepareEncoded(bytes, sourcePath: path);
  }

  Future<PreparedImage> _prepareEncoded(
    Uint8List bytes, {
    String? sourcePath,
  }) async {
    final buffer = await ui.ImmutableBuffer.fromUint8List(bytes);
    final descriptor = await ui.ImageDescriptor.encoded(buffer);
    final target = _fit(descriptor.width, descriptor.height, maxSide: 640);
    final codec = await descriptor.instantiateCodec(
      targetWidth: target.$1,
      targetHeight: target.$2,
    );

    try {
      final frame = await codec.getNextFrame();
      final image = frame.image;
      try {
        return await _prepareUiImage(image, sourcePath: sourcePath);
      } finally {
        image.dispose();
      }
    } finally {
      codec.dispose();
      descriptor.dispose();
      buffer.dispose();
    }
  }

  Future<PreparedImage> _prepareUiImage(
    ui.Image image, {
    String? sourcePath,
  }) async {
    final rgbaData = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
    if (rgbaData == null) {
      throw StateError('FreeFrame could not read that image.');
    }

    final rgba = rgbaData.buffer.asUint8List();
    final pixelCount = image.width * image.height;
    final rgb = Uint8List(pixelCount * 3);
    var src = 0;
    var dst = 0;
    for (var i = 0; i < pixelCount; i++) {
      rgb[dst++] = rgba[src++];
      rgb[dst++] = rgba[src++];
      rgb[dst++] = rgba[src++];
      src++; // alpha
    }

    final previewData = await image.toByteData(format: ui.ImageByteFormat.png);
    return PreparedImage(
      rgb: rgb,
      width: image.width,
      height: image.height,
      previewBytes: previewData?.buffer.asUint8List(),
      sourcePath: sourcePath,
    );
  }

  Future<PreparedImage> fromGenerated(ui.Image image) {
    return _prepareUiImage(image);
  }

  (int, int) _fit(int width, int height, {required int maxSide}) {
    var w = width.toDouble();
    var h = height.toDouble();
    final longest = w > h ? w : h;
    if (longest > maxSide) {
      final scale = maxSide / longest;
      w *= scale;
      h *= scale;
    }

    int snap(double value) {
      final rounded = (value / 64).round() * 64;
      return rounded.clamp(64, maxSide);
    }

    return (snap(w), snap(h));
  }
}
