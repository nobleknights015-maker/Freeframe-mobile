# Plushbound MV / Trinity Style Calibration

Status: bounded style calibration complete for character, enemy, and environment masters; guardian remains unresolved. Full production remains locked.

## Goal

Move FreeFrame rendering away from soft early-2000s anime / visual-novel styling and toward the user's reference target: modern fantasy JRPG promotional art with MV-like readability and Trinity-like color/material polish.

## Character comparison

All character comparisons used the same adult subject, seed `220218`, dimensions `768x1024`, V3.2 character composition preset, SDXL base 1.0, and three render profiles: `plushbound_mv`, `plushbound_trinity`, and `plushbound_hybrid`.

### Run 1 — trailing style tokens

Result: all three outputs were byte-identical. The style profile text had been appended after a long V3.2 production prompt, so the useful style difference fell outside the effective text-encoder window. This run was rejected as a style comparison.

### Run 2 — style-first tokens

Result: profiles became visually distinct, proving the style steering was active. MV and Hybrid became close-up portraits, while Trinity retained a full-body composition. This showed that putting a long style block first could crowd out V3.2 framing/anatomy instructions.

### Run 3 — compact style inserted after subject

Style version: `mt1.2`.

Result:
- MV: polished modern anime portrait, but still biased toward close framing.
- Trinity: full-body adult character, coherent anatomy, vivid controlled colors, clean anime features, stronger material separation, and the closest match to the supplied MV/Trinity references.
- Hybrid: polished portrait, but still biased toward close framing.

Decision: `plushbound_trinity` is the validated default for `plushbound_character` masters.

## Guardian / enemy / environment comparison

A bounded six-image same-seed comparison tested frozen V3.2 baseline versus `plushbound_trinity` for one representative Guardian, enemy, and environment master.

### Guardian

Both baseline and Trinity produced an unacceptable four-view/model-sheet composition instead of one centered Guardian. Trinity also introduced unwanted wing-like morphology. Trinity is therefore **not** promoted for Guardians. Guardian remains on the frozen V3.2 style path and requires a dedicated composition repair before another style decision.

### Enemy

Baseline produced a coherent quadruped but with a mostly monochrome sketch-like finish. Trinity preserved a single four-legged battle creature while adding stronger modern anime/JRPG color, lighting, silhouette definition, and environmental separation. Trinity is promoted for `plushbound_enemy` masters.

### Environment

Both versions produced coherent outdoor Elyndor landscapes. Trinity retained the traversable landscape/path composition while improving color separation and the brighter contemporary JRPG promotional finish. Trinity is promoted for `plushbound_environment` masters.

## Production decision

Validated Trinity defaults:
- `plushbound_character`
- `plushbound_enemy`
- `plushbound_environment`

Not validated / unchanged:
- `plushbound_guardian` — V3.2 baseline retained pending composition repair.

MV and Hybrid remain available as optional profiles for portrait-oriented experiments; they are not current full-production defaults.

## Safety / authorization

- Full 22k+ production batch: **not authorized**.
- Production style policy version: `style-policy-v2`.
- Render style version: `mt1.2`.
- V3.2 composition constraints remain intact.
