# 0008 - Carried extensions: SourceKind, cross-source identity, snapshot metrics, scheduling

**Status:** accepted

## Context

A handful of additions extend the foundation's literal schema in service of behavior the
foundation explicitly requires. They are grouped here.

## Decisions

### `SourceKind` beyond the spec's DDL shorthand

[1-collection.md](../foundation/1-collection.md)'s DDL lists `web | rss | sitemap | mbox |
mcp | reflector` as generic adapter kinds. The spec narrative and tooling tables also
enumerate the concrete sources the principal collects: Slack, GitHub, Discourse, Discord, and
Reddit (each with a canonical-id namespace, a tooling row, and mention in the opening
paragraph). `SourceKind` includes all of them. The DDL is a shorthand for the column type,
not a closed enumeration; all five API/chat adapter kinds are spec-intended. This is the
extensibility the spec calls for, not a contradiction.

### Cross-source identity: `canonical_id` + `fingerprint` + `content_hash_fuzzy`

1-collection.md's "Cross-source identity" section defines both a namespace-prefixed
`canonical_id` and a `fingerprint = sha256(canonical_url || normalized_title ||
first_500_chars)`. These are modeled as fields on `ContentRow` exactly as specified.

`content_hash_fuzzy` is a third identity mechanism from 1-collection.md's "Deduplication"
section: NFKC + casefold + punctuation-strip hash for near-exact dedup of the same text with
Unicode/whitespace variation. It is distinct from `fingerprint`, which collapses
separate-URL syndication of the same story. Both live on `ContentRow` and on the `Identity`
result type (the deduper seam's output).

### Snapshot metrics (`MetricSnapshotRow` + `MetricKind`)

The foundation's stance that cumulative engagement is captured as periodic snapshots (never
one row per increment) is pinned into the data model with `MetricSnapshotRow`, so the
"snapshot, not per-tick" policy is structural rather than a convention. `MetricKind`
(`reactions` | `upvotes` | `stars` | `views`) enumerates the engagement metrics the current
source adapters can produce; the enum is extensible as new adapters land.

### Source scheduling fields

The cadence in [1-collection.md](../foundation/1-collection.md) is per-source. To support a
per-source poll loop, `SourceRow` carries `cadence_kind`, `poll_interval_seconds`,
`last_swept_at`, `next_run_at`, and failure-tracking fields. These scheduling/lifecycle
fields remain on `SourceRow` (the mutable wrapper), while the immutable identity fields live
on `SourceIdentity` (see ADR [0009](0009-source-identity-split.md)). The `urls`/`contents`
split is kept verbatim from the spec (dedup-across-mirrors).

## Consequences

- The data model can represent every source the principal collects today.
- All additions are faithful elaborations of behavior the foundation already mandates.
