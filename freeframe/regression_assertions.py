from pathlib import Path

APP = Path('app')

required = {
    'android/app/src/main/AndroidManifest.xml': [
        'android:largeHeap="true"',
        'android:label="FreeFrame Mobile"',
    ],
    'lib/img2img_page.dart': [
        "allowedExtensions: ['safetensors', 'ckpt', 'gguf']",
        'maxWidth: 1280',
        'maxHeight: 1280',
    ],
    'lib/inpainting_page.dart': ['maxWidth: 1280', 'maxHeight: 1280'],
    'lib/outpainting_page.dart': ['maxWidth: 1280', 'maxHeight: 1280'],
    'lib/upscaler_page.dart': ['maxWidth: 1280', 'maxHeight: 1280'],
}

for rel, needles in required.items():
    p = APP / rel
    if not p.exists():
        raise SystemExit(f'Missing expected source file: {p}')
    text = p.read_text(encoding='utf-8')
    for needle in needles:
        if needle not in text:
            raise SystemExit(f'Regression assertion failed: {needle!r} missing from {rel}')

# Guard against reintroducing the original Img2Img folder-first model picker.
img2img = (APP / 'lib/img2img_page.dart').read_text(encoding='utf-8')
if '.getDirectoryPath(initialDirectory: modelDirPath)' in img2img:
    raise SystemExit('Regression assertion failed: Img2Img still uses folder-first model picking')

print('FreeFrame regression source assertions passed.')
