# Plush Guardian Composition Repair Validation

Status: targeted repair v2 retained; full production remains locked.

## Problem

The frozen V3.2 Guardian preset can drift into multi-view/model-sheet compositions, especially for some plush-creature prompts.

## Repair v1

Approach: reinforce exactly-one-creature / one-camera / centered single-view language.

Bounded same-seed comparison across Cloudram, Emberfox, Mossbun, and Riverotter:
- Cloudram: single-view baseline and repair.
- Emberfox: baseline single-view; repair duplicated the creature.
- Mossbun: baseline multi-view; repair remained multi-view.
- Riverotter: baseline multi-view; repair remained multi-view.

Decision: **rejected**. V1 was not reliably better than baseline.

## Repair v2

Approach: replace studio/product-like composition cues with a candid in-world outdoor scene, while keeping one complete creature body and explicitly rejecting catalog/contact-sheet/grid language.

Same four-subject bounded comparison:
- Cloudram: clean single-view scene.
- Emberfox: clean single-view scene.
- Mossbun: repaired from a multi-view sheet to a clean single-view scene.
- Riverotter: still produced a multi-view sheet.

Observed repaired first-pass single-view success on this bounded set: **3/4 (75%)**.

Decision: retain `guardian-single-view-v2` as the Guardian request repair, but do **not** trust prompt steering alone.

## Production safety net

A deterministic `panel-grid-v1` detector now identifies obvious image-spanning separators characteristic of generated contact sheets/model sheets. `production_inspector.inspect_generation` feeds that signal into the production policy as a hard rejection. `batch_executor.run_batch` already retries rejected generations with deterministic alternate seeds.

Resulting flow:

`build request -> generate -> inspect for panel grid -> reject/retry if needed -> extraction/package only after acceptance`

The detector is intentionally conservative and does not claim to solve semantic duplicate-subject detection. Additional semantic/vision inspection can be layered later.

## Current Guardian status

- Request steering: improved, v2 retained.
- Obvious panel/model-sheet rejection: automated.
- Deterministic retry path: wired and tested.
- Trinity render style: still **not** enabled for Guardians.
- Full 22k+ production: **not authorized**.
