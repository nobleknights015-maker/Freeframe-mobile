# Enemy master recovery lock

The accepted Plushbound enemy source-master catalog is locked at **640 masters**: 10 regions × 64 enemy masters. The canonical durable source is stored in the ChatGPT Library folder `/Plushbound/Recovery/EnemyMasters` as two ZIP parts because Library files are limited to 512 MB each.

Repository code must treat `enemy_master_archive_lock.json` as the immutable recovery contract. Before any enemy master is restored or used to build a production runtime bank, materialize both ZIP parts plus `enemy_recovery_index.json` and `enemy_archive_set_manifest.json`, then run `verify_enemy_master_archive.py`.

A nonzero verifier exit is a hard stop. Do not regenerate, substitute, infer, repair silently, or fall back to replay/placeholder imagery.

The deterministic imagery in `plushbound_enemy_runtime_production.py` exists for the runtime replay/canary path. It is **not** an accepted source-master recovery path. The older recovery/reference pack is also non-runtime and must not be substituted for these masters.

Guardian assets, Guardian recovery indexes, and Guardian banking workflows are unrelated to this archive and must remain read-only and untouched during enemy recovery.
