# External Reference Profiles

This directory stores metadata-only structural calibration profiles for external engines/assets used as compatibility references.

## RPG Maker MV

`rpg_maker_mv_reference_v1.json` records measured folder/category counts, canonical sheet geometry, image modes, and limited transparency statistics from a user-supplied RPG Maker MV asset archive.

The profile is reference-only. It is not a production art source.

Rules:

- Do not commit RPG Maker MV image pixels into this repository as Plushbound production assets.
- Do not crop, repack, trace, or derive Plushbound runtime pixels from RPG Maker MV assets.
- Do not use external asset hashes as Plushbound approval attestations.
- Use the profile only to calibrate dimensions, grid structure, readability targets, category conventions, and World Editor compatibility behavior.
- All runtime art must remain newly created Plushbound artwork and must enter through the Vera approval + SHA-256 attestation production lane.

The measured MV A5 geometry is 384 x 768 px on a 48 x 48 grid (8 columns x 16 rows, 128 slots), which confirms the locked Plushbound `WORLD_TILE_ASSET_V1` canvas/grid dimensions are structurally aligned with MV A5.
