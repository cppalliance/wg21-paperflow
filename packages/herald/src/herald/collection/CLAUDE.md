# herald.collection - Agent Rules

The collection layer: the pure-Python, no-LLM ingestion engine. See
[`../../../docs/foundation/1-collection.md`](../../../docs/foundation/1-collection.md) for the
authoritative spec and the package-root [`../CLAUDE.md`](../CLAUDE.md) for package-wide and
cross-layer rules. This file holds the collection-layer invariants.

## Module map

- `enums.py` - all `StrEnum` contract vocabularies (event/source/content/state kinds).
- `records.py` - frozen `@dataclass` row types (one per foundation table), the framework
  unions (`Candidate`, `Cursor`, `Window`), the injected-seam result types
  (`FetchResult`/`ExtractResult`/`Identity`), and the `*_to_json`/`*_from_json` codecs.
- `errors.py` - the `HeraldError` exception hierarchy.
- `storage/` - the `StorageBackend` ABC (and, later, `SqliteBackend` + `BlobStore`).
- `events/` - outbox builders + the cursor-driven consumer loop.
- `change/` - per-transport `ChangeStrategy` implementations.
- `normalize/` `fetch/` `extract/` `dedup/` - the polite-fetch + content pipeline seams.
- `sources/` - the `SourceAdapter` Protocol + concrete adapters.
- `persons/` - mechanical (no-LLM) person observation.
- `schedule/` `registry/` `obs/` - per-source cadence, config/credentials, observability.
- `orchestrator.py` - `run_sweep`, the composition point for the nine-component pipeline.

## Invariants

- **No LLM here.** Fetch/normalize/extract/dedup/change-detect/person-observe are classical
  Python. LLMs enter only at downstream layers (intelligence, writer, editorial).
- **The seven `EventKind`s are fixed.** New semantics are payload annotations, not new kinds
  (e.g. `EventOrigin`).
- **Adapters are pure producers.** An adapter yields a `Candidate` (`Discovered` for cheap
  listings, `Fetched` when the poll already has bytes); it never writes storage, emits events,
  or advances cursors.
- **Candidate / Cursor / Window are typed unions.** `Candidate = Discovered | Fetched`;
  `Cursor = Timestamp | MonotonicId | ByteOffset | OpaqueToken | Composite`;
  `Window` range = `TemporalWindow | ByteRangeWindow | CurrentOnlyWindow` (progress axes
  differ per source). Cursor and Window round-trip via tagged JSON; an unknown `kind` raises
  `ValueError`.
- **Window authority rule.** `cursor` is the single forward resume position; `window.range`
  is operator intent (a first-sweep floor / `until` ceiling); `BackfillState` drives backward
  extension so the forward cursor never rewinds. No dual temporal authority.
- **Sources vs groups via a `role` discriminator.** `role=source` rows carry a `SourceKind`
  (pollable adapter); `role=group` rows carry a `GroupKind`
  (`github_org`/`reflector_host`/`discord_guild`) and expand into child sources (`parent_id`).
  `SourceKind` stays the clean pollable vocabulary; group expansion is a discovery step, not
  `poll`.
- **Snapshot metric policy.** Cumulative engagement (reactions/upvotes/stars) is captured as
  periodic `MetricSnapshotRow` snapshots, never one row per increment.
- **`source_uid` is the source natural key** (deterministic), so cross-instance import can
  upsert/remap by natural key. Every migration-relevant table has a natural key.
- **Backfill event provenance.** Backfilled content is emitted with `EventOrigin.BACKFILL`
  (see the consumer matrix below).
- **Transactional-outbox write order is law.** Blob first (content-addressed, idempotent),
  then ONE transaction writes the metadata rows + `collection_events` + the advanced cursor.
  `record_item` is the only place an event becomes durable; its commit inputs are keyword-only.
- Add a row type for every foundation table; add a payload field, not a new `EventKind`, for
  new event semantics.

## Downstream consumer matrix (collection_events)

Consumers are registrations (a `consumer_cursors` row + a `process(event)` fn) owned by later
layers, not built in this package. Delivery is at-least-once, so consumers must be idempotent.

| consumer | reads | origin filter |
|----------|-------|---------------|
| intelligence (topics) | content_first_seen, content_changed | live only |
| intelligence (dossiers) | person_candidate_observed, content_first_seen/changed | all origins |
| candidate_harvester | content_first_seen | all origins |
| research_desk | content_first_seen, content_changed, content_re_extracted | all origins |
| finetune_export | content_first_seen, content_re_extracted | all origins |
| writer (generation) | (derives from intelligence topics / catalog) | live only |

## What this PR contains

Types + contracts + skeleton only: enums, records (incl. the Window/range model and the
group-source + migration fields), the `SourceAdapter` Protocol seam, and the `StorageBackend`
ABC. No adapters, orchestrator body, scheduler, registry validation, or group-expansion logic
yet - those land in later milestones without changing these types.
