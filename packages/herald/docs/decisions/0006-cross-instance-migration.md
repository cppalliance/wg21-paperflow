# 0006 - Cross-instance migration and the logical interchange contract

**Status:** accepted (enablers now; tooling later)

## Context

A practical workflow is to run the collector locally (on SQLite + a local blob dir), pull an
all-time archive, then move it to a dev/prod instance running Postgres. Because source and
target run **different engines**, a single literal DB dump does not transfer. The foundation
already provides the hard portability primitives: content-addressed blobs keyed by sha256
([1-collection.md](../foundation/1-collection.md) "Content extraction and dedup"), natural/content
identity on the heavy tables (`contents.content_hash_text` PK, `urls.url_syntactic` UNIQUE,
`person_handle (platform, handle)`, normalized `person_name_variant`), and an append-only
event log with replay-from-cursor idempotent consumers (1-collection.md's transactional outbox).
The one gap: `sources` was keyed only by a surrogate id, so it could not be upserted by
natural key across instances.

## Decision

Add the remaining **enablers** to the data model + contract (the exporter/importer + CLI are
a dedicated later PR):

1. `SourceIdentity.source_uid` (exposed on `SourceRow` via a read-through property) - a
   deterministic UNIQUE natural key derived from `role` + (`kind`/`group_kind`) + a stable
   hash of identity-bearing config. Now every migration-relevant table has a natural key,
   so an importer upserts and remaps surrogate FKs (`urls.source_id`, `parent_id`, event
   payload ids). The `SourceIdentity`/`SourceRow` split (ADR
   [0009](0009-source-identity-split.md)) guarantees that `source_uid` is stable across
   scheduling state changes by construction.
2. `StorageBackend.export_table(name)` / `import_rows(name, rows, *, on_conflict)` - an
   abstract interchange seam so both backends implement one shape.
3. The interchange contract (documented, not built): content-addressed blob sync (copy the
   blob tree / push to object storage - idempotent), per-table NDJSON logical export, and
   import = upsert by natural key + remap FKs; for a fresh target, reassign
   `collection_events` ids monotonically and reset consumer cursors to 0 (replay rebuilds
   downstream state). The forward-only cursor + `BackfillState` model means an imported
   archive's resume position transfers cleanly.

## Consequences

- Local-collect -> prod-import is supported by design, across engines, collision-safe.
- The interchange is *logical*, not a binary dump; that is the price of cross-engine portability.
- This PR ships the natural key + the ABC seam only.
