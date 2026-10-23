# Plushbound MV / Trinity Style Calibration

Status: bounded character-style calibration complete; full production remains locked.

## Goal

Move FreeFrame character rendering away from soft early-2000s anime / visual-novel styling and toward the user's reference target: modern fantasy JRPG promotional art with MV-like character readability and Trinity-like color/material polish.

## Bounded comparisons

All comparisons used the same adult character subject, seed `220218`, dimensions `768x1024`, V3.2 character composition preset, SDXL base 1.0, and three render profiles: `plushbound_mv`, `plushbound_trinity`, and `plushbound_hybrid`.

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

## Production decision

`plushbound_trinity` is the validated default render style for `plushbound_character` masters.

This decision is intentionally scoped to character masters only. Guardian, enemy, and environment masters remain on the frozen V3.2 rendering behavior until each category receives its own bounded style validation.

MV and Hybrid remain available as optional profiles for portrait-oriented experiments; they are not the default full-body character production style.

## Safety / authorization

- Full 22k+ production batch: **not authorized**.
- Production style policy version: `style-policy-v1`.
- Character render style version: `mt1.2`.
- V3.2 composition constraints remain intact.
