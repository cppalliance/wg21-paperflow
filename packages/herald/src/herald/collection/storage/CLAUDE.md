# herald.collection.storage - Agent Rules

The persistence seam. One ABC, two backends (SQLite for dev/test now; Postgres/Django in
production later), plus a content-addressed blob store.

## Invariants

- `StorageBackend` is an ABC; it must stay ORM-agnostic (no SQL or Django leaking into the
  signatures - rows are the frozen `records.py` dataclasses, not engine objects).
- **Write order is law (transactional outbox):** write the blob first (content-addressed,
  idempotent), then ONE transaction writes metadata rows + `collection_events` + the
  advanced cursor. `record_item` is the only durable-commit method and its commit inputs
  are keyword-only so callers can't transpose them positionally.
- Blobs are addressed by `sha256` of the bytes; the store is `put`/`get`/`exists`/
  `list_prefix` only - no update/delete in the hot path (immutability enables dedup).
- Every migration-relevant table is reachable by a **natural key** (`source_uid`,
  `content_hash_text`, `url_syntactic`, `(platform, handle)`); the `export_table` /
  `import_rows` seam exists so cross-instance interchange upserts by natural key and
  remaps surrogate FKs.
- This PR ships the ABC (and `errors.py`) only; the concrete `SqliteBackend`, `BlobStore`,
  and schema DDL land in a later milestone.
