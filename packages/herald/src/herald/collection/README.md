# Herald collection layer

The pure-Python, no-LLM ingestion engine: it discovers sources, polls them on a per-source
cadence, fetches politely, normalizes/extracts/dedups content, observes people mechanically,
and records everything through a transactional outbox (`collection_events`) for downstream
layers to consume.

The authoritative specification is
[`docs/foundation/1-collection.md`](../../../docs/foundation/1-collection.md); design deviations
are in [`docs/decisions`](../../../docs/decisions); start in
[`docs/onboarding`](../../../docs/onboarding). Agent invariants for this layer are in
[`CLAUDE.md`](CLAUDE.md).

## Status

This is the first reviewable slice: **types + contracts + skeleton**. It ships the contract
vocabulary (enums, frozen row/result types, the `Candidate`/`Cursor`/`Window` unions), the
typed range model and group-source fields, the cross-instance migration `source_uid` +
interchange seam, the `EventOrigin` provenance contract, the `SourceAdapter` Protocol, and
the `StorageBackend` ABC. Backends, adapters, the orchestrator body, the scheduler, and the
registry land in later milestones without changing these types.

## Layout

```
herald/collection/
  __init__.py  CLAUDE.md
  enums.py  records.py  errors.py     contract vocabulary + frozen types + exceptions
  orchestrator.py                     run_sweep (composition point)
  storage/  events/  change/  normalize/  fetch/  extract/
  dedup/    sources/ persons/ schedule/ registry/ obs/
```

Import surface: `herald.collection.records`, `herald.collection.storage`, etc. The top-level
`herald` namespace stays light so sibling layers (intelligence, writer, editorial) can be
added later.

## The nine-component pipeline

source adapter -> normalize -> fetch -> change detection -> extract -> dedup -> person
observation -> record (transactional outbox) -> consume. The orchestrator
(`herald.collection.orchestrator.run_sweep`) is the composition point that runs one source
through these steps; see [`docs/onboarding/overview.md`](../../../docs/onboarding/overview.md).
