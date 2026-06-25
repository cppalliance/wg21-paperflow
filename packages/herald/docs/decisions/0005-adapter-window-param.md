# 0005 - Adapter `poll(cursor, *, window=None)`

**Status:** accepted

## Context

[1-collection.md](../foundation/1-collection.md) gives the adapter one job: "turn a source into
a stream of fetch candidates," driven by an incremental cursor. Once collection ranges are
modeled (ADR [0002](0002-window-range-model.md)), the range must be enforceable at the point
that actually talks to the source - the adapter - otherwise a fresh or backfilling source
cannot be bounded and the slow-first-run problem returns.

## Decision

Extend the adapter contract to
`async def poll(self, cursor, *, window=None) -> AsyncIterator[PolledItem]`:

- `cursor` stays the forward resume position (positional).
- `window` is **keyword-only** so it cannot be transposed with `cursor`.
- The adapter must respect the window's range floor/ceiling and `ThrottleCeilings`.
- `PolledItem` pairs each `Candidate` with the post-item resume `Cursor`, so the orchestrator
  advances the cursor atomically at commit time. Adapters remain pure producers - they never
  write storage, emit events, or advance cursors.

## Consequences

- One uniform seam carries both incremental resume and bounded ranges.
- Steady-state callers pass no `window` (default `None` = "use the source's stored window").
- The Protocol lands now; concrete adapters consume `window` in a later milestone.
