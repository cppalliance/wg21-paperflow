# 0007 - Backfill event provenance (`EventOrigin`)

**Status:** accepted

## Context

Backfill pulls **past** content for data-keeping and content enhancement - the research-desk
semantic index, the fine-tuning corpus, and person dossiers
([1-collection.md](../foundation/1-collection.md) "Continuous ingestion is also the fine-tuning
corpus"; [3-writer.md](../foundation/3-writer.md) research desk). It is explicitly **not** meant
to generate articles, which need fresh material. But backfill must still emit
`collection_events`, because the archival/enhancement consumers are cursor-driven and would
otherwise miss exactly the historical content backfill exists to feed. Suppressing events is
therefore wrong; the events need to carry their provenance.

## Decision

Add an `EventOrigin` enum (`live` | `backfill`) carried as an `origin` field in the event
payload (default `live`). The orchestrator stamps `origin=backfill` for items produced by a
`BackfillState` pass. The seven canonical event kinds are unchanged - provenance is a payload
annotation, not a new kind.

**Consumer contract** (see the package `CLAUDE.md` consumer matrix): generation-driving
consumers (the writer's catalog/triage, intelligence topic building) MUST ignore
`origin=backfill`; archival/enhancement consumers (research-desk embedder, fine-tune export,
the dossier side of intelligence) process all origins.

## Consequences

- Historical content reaches the archive/corpus without leaking into "news."
- Stricter than relying on the writer's recency window alone (a backfill re-pulling recent
  dates could otherwise leak into generation).
- This PR ships the enum + the payload convention + the docs contract; the orchestrator that
  sets it and the consumers that filter it are later layers.
