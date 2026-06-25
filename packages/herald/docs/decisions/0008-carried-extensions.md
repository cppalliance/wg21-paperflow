# 0008 - Carried extensions: SourceKind, cross-source identity, snapshot metrics, scheduling

**Status:** accepted

## Context

A handful of additions extend the foundation's literal schema in service of behavior the
foundation explicitly requires. They are grouped here.

## Decisions

### `SourceKind` beyond the spec's enumerated set

[1-collection.md](../foundation/1-collection.md) lists `web | rss | sitemap | mbox | mcp |
reflector` as example kinds while insisting adapters live behind a common interface so new
sources "do not touch the rest of the system." The principal also collects GitHub, Discourse,
Discord, and Reddit. `SourceKind` therefore includes `github`/`discourse`/`discord`/`reddit`
in addition to the spec set. This is the extensibility the spec calls for, not a contradiction.

### Cross-source identity: `canonical_id` + `fingerprint`

1-collection.md's "Cross-source identity" section defines both a namespace-prefixed
`canonical_id` and a `fingerprint = sha256(canonical_url || normalized_title ||
first_500_chars)`. These are modeled as fields on `ContentRow` exactly as specified.

### Snapshot metrics (`MetricSnapshotRow`)

The foundation's stance that cumulative engagement is captured as periodic snapshots (never
one row per increment) is pinned into the data model with `MetricSnapshotRow`, so the
"snapshot, not per-tick" policy is structural rather than a convention.

### Source scheduling fields

The cadence in [1-collection.md](../foundation/1-collection.md) is per-source. To support a
per-source poll loop, `SourceRow` carries `cadence_kind`, `poll_interval_seconds`,
`last_swept_at`, `next_run_at`, and failure-tracking fields. The `urls`/`contents` split is
kept verbatim from the spec (dedup-across-mirrors).

## Consequences

- The data model can represent every source the principal collects today.
- All additions are faithful elaborations of behavior the foundation already mandates.
