from pathlib import Path

# Standard profile for newer Android phones with more physical RAM.
# The shared engine patch first applies the conservative 448x448 / 15-step
# defaults. This patch raises the public Standard build to 512x512 / 20 steps
# while keeping the same single native session and Flash Attention path.

chat_path = Path('app/lib/src/chat_screen.dart')
chat = chat_path.read_text(encoding='utf-8')

for old, new in [
    ('        width: 448,\n', '        width: 512,\n'),
    ('        height: 448,\n', '        height: 512,\n'),
    ('        steps: 15,\n', '        steps: 20,\n'),
]:
    if old not in chat:
        raise SystemExit(f'Expected standard-profile marker not found: {old.strip()}')
    chat = chat.replace(old, new, 1)

chat_path.write_text(chat, encoding='utf-8')

session_path = Path('app/lib/src/model_session.dart')
session = session_path.read_text(encoding='utf-8')
for old, new in [
    ('    this.width = 448,\n', '    this.width = 512,\n'),
    ('    this.height = 448,\n', '    this.height = 512,\n'),
    ('    this.steps = 15,\n', '    this.steps = 20,\n'),
]:
    if old not in session:
        raise SystemExit(f'Expected standard session marker not found: {old.strip()}')
    session = session.replace(old, new, 1)

session_path.write_text(session, encoding='utf-8')
print('FreeFrame Standard profile applied: 512x512, 20 steps')
