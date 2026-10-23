# FreeFrame Extraction Smoke Success

Validated run: `39896306787` (run #5)
Artifact: `freeframe-extraction-smoke` (`12476996224`)
Artifact digest: `sha256:5e0ccd33f9ff60774d2dd788321346adb799acf73168666654026b5100a09def`

## Result

The bounded one-asset SDXL -> BiRefNet extraction smoke completed successfully end-to-end.

- Asset class: `character_master`
- Seed: `8201`
- Source/output dimensions: `768x1024`
- Generation time: `9.909s`
- Extraction time: `1.054s`
- Provider: `birefnet`
- Model: `ZhengPeng7/BiRefNet`
- Foreground fraction: `0.25303`
- Foreground bbox: `[209, 86, 587, 965]`
- Bbox width fraction: `0.492188`
- Bbox height fraction: `0.858398`
- Edge alpha fraction: `0.0`

## Visual QA

The extracted RGBA result was composited against both white and black backgrounds. The subject silhouette, hat, pack/straps, handheld bag, coat, legs, and boots separated cleanly with no obvious retained scene chunks. The output has a full 0-255 alpha range and transparent image corners.

## Production implication

Real GPU subject extraction is now proven. This does **not** authorize the full asset batch. Production should continue to route subject masters through extraction and reject/retry failures via the existing deterministic retry path.
