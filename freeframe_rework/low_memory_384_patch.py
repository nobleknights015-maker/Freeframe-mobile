from pathlib import Path

# Ultra-safe physical-device profile for the Moto G 4 GB target.
# The 448x448 build still crashed instantly when native sampling started, so
# skip the intermediate 384-only test and reduce several memory contributors
# at once while keeping the Q4_0 model itself unchanged.

chat_path = Path('app/lib/src/chat_screen.dart')
chat = chat_path.read_text(encoding='utf-8')

# Engine patch creates the 448x448 / 15-step profile first. Replace that with
# the ultra-safe 320x320 / 12-step profile for this build.
for old, new in [
    ('        width: 448,\n', '        width: 320,\n'),
    ('        height: 448,\n', '        height: 320,\n'),
    ('        steps: 15,\n', '        steps: 12,\n'),
]:
    if old not in chat:
        raise SystemExit(f'Expected chat safe-profile marker was not found: {old.strip()}')
    chat = chat.replace(old, new, 1)
chat_path.write_text(chat, encoding='utf-8')

session_path = Path('app/lib/src/model_session.dart')
session = session_path.read_text(encoding='utf-8')
for old, new in [
    ('    this.width = 448,\n', '    this.width = 320,\n'),
    ('    this.height = 448,\n', '    this.height = 320,\n'),
    ('    this.steps = 15,\n', '    this.steps = 12,\n'),
]:
    if old not in session:
        raise SystemExit(f'Expected session safe-profile marker was not found: {old.strip()}')
    session = session.replace(old, new, 1)
session_path.write_text(session, encoding='utf-8')

# Keep reference/edit images small as well. This reduces the RGB source buffer
# retained during img2img and prevents a large decoded reference from competing
# with native sampling allocations.
image_path = Path('app/lib/src/image_input.dart')
image_text = image_path.read_text(encoding='utf-8')
old_max = '    final target = _fit(descriptor.width, descriptor.height, maxSide: 640);\n'
new_max = '    final target = _fit(descriptor.width, descriptor.height, maxSide: 320);\n'
if old_max not in image_text:
    raise SystemExit('Expected reference max-side marker was not found')
image_text = image_text.replace(old_max, new_max, 1)
image_path.write_text(image_text, encoding='utf-8')

print('FreeFrame Moto G ultra-safe profile applied: 320x320, 12 steps, 320px refs')
