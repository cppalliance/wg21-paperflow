# herald.collection.sources - Agent Rules

Source adapters. Only the `SourceAdapter` Protocol seam exists today; concrete adapters
(RSS, reflector mbox, GitHub) land in later milestones. See `SOURCES.md` for the matrix.

## Invariants

- An adapter implements `async def poll(self, cursor, *, window=None) -> AsyncIterator[PolledItem]`.
  It is the *only* component that knows a source's wire format.
- Adapters yield a `Candidate`: `Discovered` (a cheap listing entry - URL + hint, fetched
  later) or `Fetched` (bytes already in hand, e.g. an mbox message or an API record).
  Pick `Fetched` only when polling already paid for the bytes.
- Adapters are **pure producers**: they never write storage, never emit `collection_events`,
  never advance cursors. The orchestrator does all of that.
- `cursor` is the forward resume position; `window` is operator intent (range floor/ceiling
  + backfill target). Adapters must respect `window` ceilings (`ThrottleCeilings`) so a
  fresh or backfilling source stays bounded.
- Group expansion (a `role=group` row -> child `role=source` rows) is a separate discovery
  step, **not** `poll`. Keep `SourceKind` the clean pollable vocabulary; group kinds live
  in `GroupKind`.
- New source type = new adapter module + a `SourceKind` value + a registry config schema.
  No edits to the orchestrator.
