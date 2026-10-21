import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:image/image.dart' as img;
import 'package:image_picker/image_picker.dart';

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
  final ImagePicker _picker = ImagePicker();

  Future<PreparedImage?> pickReference() async {
    final picked = await _picker.pickImage(
      source: ImageSource.gallery,
      maxWidth: 1024,
      maxHeight: 1024,
      imageQuality: 90,
    );
    if (picked == null) return null;
    final bytes = await picked.readAsBytes();
    return _prepareEncoded(bytes, sourcePath: picked.path);
  }

  PreparedImage _prepareEncoded(Uint8List bytes, {String? sourcePath}) {
    final decoded = img.decodeImage(bytes);
    if (decoded == null) {
      throw StateError('FreeFrame could not decode that image.');
    }

    final target = _fit(decoded.width, decoded.height, maxSide: 768);
    var working = decoded;
    if (target.$1 != decoded.width || target.$2 != decoded.height) {
      working = img.copyResize(
        decoded,
        width: target.$1,
        height: target.$2,
        interpolation: img.Interpolation.average,
      );
    }

    final rgb = Uint8List(working.width * working.height * 3);
    var offset = 0;
    for (final pixel in working) {
      rgb[offset++] = pixel.r.toInt();
      rgb[offset++] = pixel.g.toInt();
      rgb[offset++] = pixel.b.toInt();
    }

    return PreparedImage(
      rgb: rgb,
      width: working.width,
      height: working.height,
      previewBytes: Uint8List.fromList(img.encodeJpg(working, quality: 82)),
      sourcePath: sourcePath,
    );
  }

  Future<PreparedImage> fromGenerated(ui.Image image) async {
    final data = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
    if (data == null) throw StateError('Could not read generated image pixels.');
    final rgba = data.buffer.asUint8List();
    final source = img.Image.fromBytes(
      width: image.width,
      height: image.height,
      bytes: rgba.buffer,
      numChannels: 4,
    );
    final jpg = Uint8List.fromList(img.encodeJpg(source, quality: 88));
    return _prepareEncoded(jpg);
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
