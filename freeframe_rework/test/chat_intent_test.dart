import 'package:flutter_test/flutter_test.dart';
import '../lib/src/chat_intent.dart';

void main() {
  const parser = ChatIntentParser();

  test('plain request routes to text to image', () {
    final result = parser.parse(
      text: 'Make a rainy neon city at night',
      hasAttachedImage: false,
      hasPreviousImage: false,
    );
    expect(result.action, FreeFrameAction.textToImage);
  });

  test('attached reference routes to image to image', () {
    final result = parser.parse(
      text: 'Put this character in a forest',
      hasAttachedImage: true,
      hasPreviousImage: false,
    );
    expect(result.action, FreeFrameAction.imageToImage);
  });

  test('edit language with reference routes to edit', () {
    final result = parser.parse(
      text: 'Fix the hands and keep everything else the same',
      hasAttachedImage: true,
      hasPreviousImage: false,
    );
    expect(result.action, FreeFrameAction.editImage);
  });

  test('follow up can reuse previous output', () {
    final result = parser.parse(
      text: 'Make another version and use that',
      hasAttachedImage: false,
      hasPreviousImage: true,
    );
    expect(result.action, FreeFrameAction.reuseReference);
    expect(result.keepPreviousCharacter, isTrue);
  });
}
