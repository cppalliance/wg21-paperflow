# Overview

Herald is the C++ ecosystem ingestion + generation pipeline. This package implements its
first layer, **collection**: the pure-Python, no-LLM engine that ingests everything (public
and private) into a uniform store the downstream layers consume.

## The layers

Herald is a multi-layer system; each layer is a subpackage under `herald.`, specified in
[`../foundation`](../foundation):

- **Collection** (`herald.collection`, implemented) - ingest, normalize, dedup, observe
  people, and emit `collection_events`.
- **Intelligence** (planned) - identity resolution, topic/delta building, evidence packages.
- **Writer** (planned, + the research desk) - the daily article-generation pipeline.
- **Editorial** (planned, + source curation) - slate selection and the Feed Proposer.
- **People tracking** (planned) - dossiers, woven across collection/intelligence/writer.

The downstream layers run on the self-hosted LLM fleet via the `pipeline` package and share a
Postgres database (and R2 bucket) with wg21.org. Everything below describes the collection
layer, the only one built today; the package-wide and cross-layer rules are in the package
[`CLAUDE.md`](../../src/herald/CLAUDE.md).

## The nine-component pipeline

The authoritative description is [1-collection.md](../foundation/1-collection.md); the shape:

1. **Source adapter** - turns a source (rss, sitemap, mbox/reflector, mcp, github, ...) into
   a stream of candidates. The only component that knows a source's wire format.
2. **Normalize** - canonicalize URLs so mirrors collapse.
3. **Fetch** - polite, tiered HTTP (rate limiting, robots, conditional GET, signed requests).
4. **Change detection** - per-transport strategy decides new/changed/unchanged/removed.
5. **Extract** - raw bytes -> clean text + metadata; language id.
6. **Dedup** - content hashes + cross-source identity (`canonical_id`, `fingerprint`).
7. **Person observation** - mechanical name/handle matching; flag pending candidates.
8. **Record** - the transactional outbox: blob first, then one transaction writes metadata
   rows + `collection_events` + the advanced cursor.
9. **Consume** - downstream consumers replay `collection_events` from their cursor.

The orchestrator (`herald.collection.orchestrator.run_sweep`) is the composition point that
runs one source through steps 1-8; consumers (step 9) live in later layers.

## Package layout

```
herald/                      thin namespace (version + console script)
  collection/
    enums.py records.py errors.py   contract vocabulary + frozen types + exceptions
    orchestrator.py                 run_sweep (composition point)
    storage/  events/  change/  normalize/  fetch/  extract/
    dedup/    sources/ persons/ schedule/ registry/ obs/
```

Import surface: `herald.collection.records`, `herald.collection.storage`, etc.

## What exists today

Types + contracts + skeleton: the enums, the frozen row/result types, the
`Candidate`/`Cursor`/`Window` unions, the group-source + migration fields, the `EventOrigin`
provenance contract, the `SourceAdapter` Protocol, and the `StorageBackend` ABC. Backends,
adapters, the orchestrator body, the scheduler, and the registry land in later milestones -
see [../todo](../todo) - and the design rationale for every extension is in
[../decisions](../decisions).
