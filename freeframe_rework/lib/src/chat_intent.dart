enum FreeFrameAction { textToImage, imageToImage, editImage, reuseReference }

class FreeFrameIntent {
  const FreeFrameIntent({
    required this.action,
    required this.prompt,
    this.keepPreviousCharacter = false,
  });

  final FreeFrameAction action;
  final String prompt;
  final bool keepPreviousCharacter;
}

/// Lightweight first-pass interpreter for conversational image requests.
///
/// This deliberately avoids running a second large language model beside the
/// diffusion model on low-memory phones. A smarter parser can replace this
/// later without changing the chat UI or model-session contract.
class ChatIntentParser {
  const ChatIntentParser();

  FreeFrameIntent parse({
    required String text,
    required bool hasAttachedImage,
    required bool hasPreviousImage,
  }) {
    final normalized = text.trim().toLowerCase();
    final editLanguage = normalized.contains('fix ') ||
        normalized.contains('change ') ||
        normalized.contains('remove ') ||
        normalized.contains('replace ') ||
        normalized.contains('keep everything else') ||
        normalized.contains('make the ') ||
        normalized.startsWith('make it ');

    final keepCharacter = normalized.contains('same character') ||
        normalized.contains('keep her') ||
        normalized.contains('keep him') ||
        normalized.contains('keep their') ||
        normalized.contains('keep the character');

    if (hasAttachedImage && editLanguage) {
      return FreeFrameIntent(
        action: FreeFrameAction.editImage,
        prompt: text.trim(),
        keepPreviousCharacter: keepCharacter,
      );
    }

    if (hasAttachedImage) {
      return FreeFrameIntent(
        action: FreeFrameAction.imageToImage,
        prompt: text.trim(),
        keepPreviousCharacter: keepCharacter,
      );
    }

    if (hasPreviousImage && editLanguage) {
      return FreeFrameIntent(
        action: FreeFrameAction.editImage,
        prompt: text.trim(),
        keepPreviousCharacter: keepCharacter,
      );
    }

    if (hasPreviousImage &&
        (normalized.contains('use that') ||
            normalized.contains('same one') ||
            normalized.contains('another version'))) {
      return FreeFrameIntent(
        action: FreeFrameAction.reuseReference,
        prompt: text.trim(),
        keepPreviousCharacter: true,
      );
    }

    return FreeFrameIntent(
      action: FreeFrameAction.textToImage,
      prompt: text.trim(),
      keepPreviousCharacter: keepCharacter,
    );
  }
}
