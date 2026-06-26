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

## Contracts to pin when those milestones land (avoid later rework)

These foundation contracts are intentionally not frozen in the data-model PR; each must be
honored by the milestone that builds the corresponding behavior, so emitters/consumers and
persisted data do not drift:

- **Event payloads (events/outbox milestone):** pin the per-kind payload keys verbatim from
  [1-collection.md](../foundation/1-collection.md) (e.g. `content_changed` ->
  `url_id`/`old_hash`/`new_hash`) and the `origin` key (`live`/`backfill`) from
  [ADR 0007](../decisions/0007-backfill-event-provenance.md), via typed builders, before any
  events are emitted.
- **Cross-source identity (dedup milestone):** pin the `canonical_id` namespace set and the
  `fingerprint = sha256(canonical_url || normalized_title || first_500_chars)` formula in a
  builder; populate `ContentRow.content_hash_fuzzy` (the fuzzy near-exact dedup hash).
- **Change detection (orchestrator/change milestone):** implement the foundation's
  cosmetic-vs-real distinction (cosmetic -> update timestamps only, no `url_content_versions`
  row, no event; real -> new version + events). `ChangeKind` is an in-process, non-persisted
  enum today and may be reconciled then.
- **Cursor resync (reflector adapter milestone):** extend `ByteOffset` with optional resync
  fields (additive defaults so persisted `cursor_json` stays backward-compatible).
- **Deferred people-store rows/fields:** `person_alias_resolution` (merge/split audit) and
  the dossier-side `person.tsv`/`nationality`/`location` are intelligence/people-store
  concerns; add them when those layers land.

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
