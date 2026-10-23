# FreeFrame Reference Conditioning Validation

Status: bounded SDXL/IP-Adapter reference conditioning validated; full production remains locked.

## Goal

Allow FreeFrame to learn rendering language from approved example images without committing those images to the repository and without letting the reference override the requested Plushbound subject/composition.

## Storage and provenance

- Approved references are stored in the Modal Volume `freeframe-reference-cache`, not in git.
- References are content-addressed by SHA-256 and revalidated on load.
- Generation requests may use either inline reference bytes or a stored `reference_id`.
- Text-only generations reset IP-Adapter influence so a prior reference cannot bleed into later work.

## Live GPU validation

Reference smoke run `39905320310` proved the complete path:

`store reference -> commit Modal Volume -> reload by SHA-256 -> load IP-Adapter -> generate -> preserve reference metadata -> upload artifact`

The first successful synthetic reference-conditioned generation used a deliberately simple flat 2D reference and visibly inherited its graphic edge/color language, proving behavioral conditioning rather than metadata-only plumbing.

## Same-seed mode comparison

Reference smoke run `39906602560` compared one identical fox/woodland request at seed `4411` across three variants:

- Baseline: no reference conditioning.
- Balanced: scalar IP-Adapter scale `0.35` across the adapter.
- Style-only: block-specific scale `{"up": {"block_0": [0.0, 0.35, 0.0]}}`.

Result:

- **Balanced** strongly inherited the synthetic reference's silhouette/content and simplified the requested scene too aggressively.
- **Style-only** preserved the requested fox identity and woodland context substantially better while still borrowing the reference's flat outlined visual language.
- **Baseline** obeyed the prompt but had no external visual-reference influence.

## Production decision

`reference_mode = "style"` is the only reference mode approved for the production request builder.

`balanced` remains available as an explicit experiment surface but is not emitted by production requests.

Production requests using references must provide:

- a valid lowercase SHA-256 `reference_id`
- a scale between `0.0` and `1.0`
- style-only conditioning is forced by the builder

## Next validation

The next useful bounded test is a real Plushbound-owned 2D creature reference, especially the cropped Guardian/creature reference prepared from the supplied Plushbound concept sheet. This should test whether the same mechanism moves Guardian rendering away from 3D/toy presentation and toward the intended 2D stitched JRPG style.

The supplied MV and Trinity images remain directional references and should not be committed into the public repository.

## Safety / authorization

- Full 22k+ asset batch: **not authorized**.
- Reference conditioning: **GPU validated**.
- Production reference mode: **style-only**.
