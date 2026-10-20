from pathlib import Path

# FreeFrame mobile stability patches applied to the upstream Local Diffusion source.

# 1) Give Android a little more heap headroom for native model/image work.
manifest = Path('app/android/app/src/main/AndroidManifest.xml')
text = manifest.read_text(encoding='utf-8')
if 'android:largeHeap=' not in text:
    text = text.replace(
        'android:requestLegacyExternalStorage="true"',
        'android:requestLegacyExternalStorage="true"\n        android:largeHeap="true"'
    )
manifest.write_text(text, encoding='utf-8')

# 2) Downscale gallery images before Dart decodes them. This prevents a phone from
#    briefly holding a huge original + decoded image + RGB copy at the same time.
for rel in [
    'lib/img2img_page.dart',
    'lib/inpainting_page.dart',
    'lib/outpainting_page.dart',
    'lib/upscaler_page.dart',
]:
    p = Path('app') / rel
    if not p.exists():
        continue
    s = p.read_text(encoding='utf-8')
    s = s.replace(
        'picker.pickImage(source: ImageSource.gallery);',
        'picker.pickImage(\n        source: ImageSource.gallery,\n        maxWidth: 1280,\n        maxHeight: 1280,\n        imageQuality: 90,\n      );'
    )
    p.write_text(s, encoding='utf-8')

# 3) Img2Img: use a direct file picker instead of forcing the user to choose a
#    folder first, and dismiss the dialog before heavy model initialization.
p = Path('app/lib/img2img_page.dart')
s = p.read_text(encoding='utf-8')
start = """                final modelDirPath = await getModelDirectory();
                final selectedDir = await FilePicker.platform
                    .getDirectoryPath(initialDirectory: modelDirPath);

                if (selectedDir != null) {
                  final directory = Directory(selectedDir);
                  final files = directory.listSync();
                  final modelFiles = files
                      .whereType<File>()
                      .where((file) =>
                          file.path.endsWith('.safetensors') ||
                          file.path.endsWith('.ckpt') ||
                          file.path.endsWith('.gguf'))
                      .toList();

                  if (modelFiles.isNotEmpty) {
                    final selectedModel = await showShadDialog<String>(
                      context: context,
                      builder: (BuildContext context) {
                        return ShadDialog.alert(
                          constraints: const BoxConstraints(maxWidth: 400),
                          title: const Text('Select Model'),
                          description: SizedBox(
                            height: 300,
                            child: Material(
                              color: Colors.transparent,
                              child: ShadTable.list(
                                header: const [
                                  ShadTableCell.header(
                                      child: Text('Model',
                                          style: TextStyle(fontSize: 16))),
                                  ShadTableCell.header(
                                      alignment: Alignment.centerRight,
                                      child: Text('Size',
                                          style: TextStyle(fontSize: 16))),
                                ],
                                columnSpanExtent: (index) {
                                  if (index == 0)
                                    return const FixedTableSpanExtent(250);
                                  if (index == 1)
                                    return const FixedTableSpanExtent(80);
                                  return null;
                                },
                                children: modelFiles
                                    .asMap()
                                    .entries
                                    .map((entry) => [
                                          ShadTableCell(
                                            child: GestureDetector(
                                              onTap: () => Navigator.pop(
                                                  context, entry.value.path),
                                              child: Padding(
                                                padding:
                                                    const EdgeInsets.symmetric(
                                                        vertical: 12.0),
                                                child: Text(
                                                  entry.value.path
                                                      .split('/')
                                                      .last,
                                                  style: const TextStyle(
                                                      fontWeight:
                                                          FontWeight.w500,
                                                      fontSize: 14),
                                                ),
                                              ),
                                            ),
                                          ),
                                          ShadTableCell(
                                            alignment: Alignment.centerRight,
                                            child: GestureDetector(
                                              onTap: () => Navigator.pop(
                                                  context, entry.value.path),
                                              child: Text(
                                                '${(entry.value.lengthSync() / (1024 * 1024)).toStringAsFixed(1)} MB',
                                                style: const TextStyle(
                                                    fontSize: 12),
                                              ),
                                            ),
                                          ),
                                        ])
                                    .toList(),
                              ),
                            ),
                          ),
                          actions: [
                            ShadButton.outline(
                              onPressed: () => Navigator.pop(context),
                              child: const Text('Cancel'),
                            ),
                          ],
                        );
                      },
                    );

                    if (selectedModel != null) {
                      setState(() => loadingText = 'Loading Model...');
                      _initializeProcessor(
                        selectedModel,
                        useFlashAttention,
                        SDType.values.firstWhere(
                          (type) => type.displayName == selectedQuantization,
                          orElse: () => SDType.NONE,
                        ),
                        Schedule.values.firstWhere(
                          (s) => s.displayName == selectedSchedule,
                          orElse: () => Schedule.DISCRETE,
                        ),
                      );
                    }
                  }
                }
                Navigator.of(context).pop();
"""
replacement = """                final result = await FilePicker.platform.pickFiles(
                  type: FileType.custom,
                  allowedExtensions: ['safetensors', 'ckpt', 'gguf'],
                  allowMultiple: false,
                );
                if (result == null || result.files.single.path == null) {
                  return;
                }

                final selectedModel = result.files.single.path!;
                if (!mounted) return;

                // Close the settings dialog before model initialization so a
                // long native load cannot leave a modal overlay trapping input.
                Navigator.of(context).pop();
                await Future<void>.delayed(const Duration(milliseconds: 150));
                if (!mounted) return;

                setState(() => loadingText = 'Loading Model...');
                _initializeProcessor(
                  selectedModel,
                  useFlashAttention,
                  SDType.values.firstWhere(
                    (type) => type.displayName == selectedQuantization,
                    orElse: () => SDType.NONE,
                  ),
                  Schedule.values.firstWhere(
                    (s) => s.displayName == selectedSchedule,
                    orElse: () => Schedule.DISCRETE,
                  ),
                );
"""
if start not in s:
    raise SystemExit('Expected Img2Img model-picker block was not found; upstream changed.')
s = s.replace(start, replacement, 1)
p.write_text(s, encoding='utf-8')

print('FreeFrame mobile stability patches applied.')
