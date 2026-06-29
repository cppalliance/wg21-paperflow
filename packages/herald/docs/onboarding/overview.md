# Overview

Herald is the C++ ecosystem ingestion + generation pipeline: collection, people tracking,
intelligence, writer, and editorial, each a subpackage under `herald.`. Only the collection
layer is built today; see the [layer table](../../src/herald/CLAUDE.md) and
[foundation spec](../foundation) for the full scope.

## The collection pipeline

Nine components, described in [1-collection.md](../foundation/1-collection.md):

1. **Source adapter** - turns a source into a `Candidate` stream (the only wire-format-aware component).
2. **Normalize** - canonicalize URLs so mirrors collapse.
3. **Fetch** - polite, tiered HTTP (rate limiting, robots, conditional GET, signed requests).
4. **Change detection** - per-transport strategy: new / changed / unchanged / removed.
5. **Extract** - raw bytes to clean text + metadata; language id.
6. **Dedup** - content hashes + cross-source identity (`canonical_id`, `fingerprint`).
7. **Person observation** - mechanical name/handle matching; flag pending candidates.
8. **Record** - transactional outbox: blob first, then one commit writes metadata + events + cursor.
9. **Consume** - downstream consumers replay `collection_events` from their cursor.

`run_sweep` in `herald.collection.orchestrator` runs steps 1-8 for one source; consumers
(step 9) live in later layers.

## Package layout

```
herald/                      thin namespace (version + console script)
  collection/
    enums.py records.py errors.py   contract vocabulary + frozen types + exceptions
    orchestrator.py                 run_sweep (composition point)
    storage/  events/  change/  normalize/  fetch/  extract/
    dedup/    sources/ persons/ schedule/ registry/ obs/
```

## What exists today

Types + contracts + skeleton only. Backends, adapters, the orchestrator body, scheduler, and
registry land in later milestones (see [../todo](../todo)). Design rationale is in
[../decisions](../decisions); cross-layer rules in [`CLAUDE.md`](../../src/herald/CLAUDE.md).
