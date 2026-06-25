# Roadmap

A forward roadmap derived from the capabilities described in the
[foundation documents](../foundation). It is focused on the **collection layer** (the only
layer implemented) and ends with the downstream layers that follow. It tracks what remains
after this first data-model/skeleton PR; it is not a backlog mirror.

## Landed (this PR)

- Package skeleton under `herald/collection/`, the contract vocabulary (enums, frozen
  row/result types, the `Candidate` and `Cursor` unions), the typed `Window`/range model,
  group source fields, the migration `source_uid` + interchange seam, the `EventOrigin`
  provenance contract, and the `StorageBackend` ABC.

## Next (later PRs)

- Concrete `SqliteBackend` + content-addressed `BlobStore` + schema DDL + the behavioral
  storage contract.
- Change strategies, the events outbox + cursor consumer loop, the orchestrator sweep.
- Source adapters (RSS, reflector mbox, GitHub) and the per-kind registry config + factory.
- The scheduler (per-source cadence, fleet throttle) and group-expansion/discovery.
- Window enforcement at sweep time, chunked backfill, and range extension.
- Migration tooling: `export_table`/`import_rows` implementations, `herald export`/`import`
  CLI, blob sync, and an end-to-end SQLite -> Postgres round-trip test.
- Mechanical person observation and observability (structlog + prometheus).

## Beyond collection (downstream layers)

Added later as sibling subpackages under `herald.`, each specified in the foundation docs and
running on the self-hosted LLM fleet via the `pipeline` package:

- **Intelligence** - identity resolution, topic/delta building, evidence packages
  ([residue.md](../foundation/residue.md), [2-people.md](../foundation/2-people.md)).
- **Writer** - the daily article-generation pipeline and the research desk
  ([3-writer.md](../foundation/3-writer.md), [story-shapes.md](../foundation/story-shapes.md), [register-lock.md](../foundation/register-lock.md)).
- **Editorial** - slate selection and the LLM Feed Proposer for source curation
  ([residue.md](../foundation/residue.md)).
- **wg21.org integration** - the Django/Postgres adapter and Atom feed, owned by the
  wg21.org repo, not this package.
