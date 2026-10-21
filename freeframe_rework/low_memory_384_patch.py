from pathlib import Path

# Physical-device fallback after the 448x448 profile still died immediately at
# native sampling start on the Moto G 4 GB target. Keep the Q4_0 model and 15
# steps, but reduce the working image area to 384x384 to cut peak tensor/buffer
# pressure without changing the model itself.

chat_path = Path('app/lib/src/chat_screen.dart')
chat = chat_path.read_text(encoding='utf-8')

chat_width_old = '        width: 448,\n'
chat_height_old = '        height: 448,\n'
if chat_width_old not in chat or chat_height_old not in chat:
    raise SystemExit('Expected 448x448 chat safe profile was not found')
chat = chat.replace(chat_width_old, '        width: 384,\n', 1)
chat = chat.replace(chat_height_old, '        height: 384,\n', 1)
chat_path.write_text(chat, encoding='utf-8')

session_path = Path('app/lib/src/model_session.dart')
session = session_path.read_text(encoding='utf-8')

session_width_old = '    this.width = 448,\n'
session_height_old = '    this.height = 448,\n'
if session_width_old not in session or session_height_old not in session:
    raise SystemExit('Expected 448x448 session safe defaults were not found')
session = session.replace(session_width_old, '    this.width = 384,\n', 1)
session = session.replace(session_height_old, '    this.height = 384,\n', 1)
session_path.write_text(session, encoding='utf-8')

print('FreeFrame Moto G emergency-safe profile applied: 384x384, 15 steps')
