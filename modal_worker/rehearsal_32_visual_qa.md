# FreeFrame 32-Asset GPU Rehearsal — Visual QA

Run: `39882380308`
Artifact: `freeframe-production-rehearsal` (`12470983535`)
Generator style: `v3.2`
Model: `stabilityai/stable-diffusion-xl-base-1.0`

## Technical result

- 32 / 32 requested generations completed and were emitted as PNG files.
- Manifest count: 32.
- Rehearsal wall time: 624.792 seconds.
- Full batch remains explicitly unauthorized.

## Visual composition review

The bounded run confirms stable generation, but raw generation is not yet sufficient for unattended production. Six outputs visibly violated the single-scene / single-view composition requirement and should be rejected by production inspection and retried with the deterministic retry path.

| Asset | Seed | Result | Reason |
|---|---:|---|---|
| `plushbound_character-05` | 9105 | REJECT | Two-view/model-sheet style composition |
| `plushbound_enemy-03` | 9111 | REJECT | Multiple creature views / lineup composition |
| `plushbound_environment-05` | 9121 | REJECT | Split/multi-panel landscape composition |
| `plushbound_guardian-02` | 9126 | REJECT | Four-view/model-sheet composition |
| `plushbound_guardian-03` | 9127 | REJECT | Multi-view/model-sheet composition |
| `plushbound_guardian-07` | 9131 | REJECT | Multi-view/model-sheet composition |

The other 26 outputs passed this first-pass composition review for a 26/32 (81.25%) raw visual acceptance rate.

## Production decision

This rehearsal is a successful bounded GPU-generation reliability test, not approval for the full 22k+ production batch. The raw visual acceptance rate is below the production rehearsal target, so production inspection/retry must be wired before scaling.

Next engineering actions:

1. Feed composition rejection into the existing deterministic retry engine rather than endlessly revising the frozen V3.2 prompt family.
2. Preserve rejection reasons and effective retry seeds in checkpoint metadata.
3. Add the real subject-extraction backend and route extraction-required asset classes through the alpha quality gate.
4. Keep environments on the extraction bypass path.
5. Run another bounded rehearsal only after inspection/retry and extraction routing are integrated.
