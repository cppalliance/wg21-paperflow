# 0009 - `SourceRow`/`SourceIdentity` two-layer identity split

**Status:** accepted

## Context

`SourceRow` originally held 20 fields spanning identity (`source_uid`, `name`, `role`,
`kind`, `group_kind`, `config_json`), group hierarchy (`parent_id`, `window_inherited`),
lifecycle state (`enabled`, `state`, `access_state`), scheduling (`cadence_kind`,
`poll_interval_seconds`, `next_run_at`, `last_swept_at`), and error tracking (`last_error`,
`consecutive_failures`). Mixing immutable identity with mutable scheduling in a single flat
struct creates two problems:

1. The natural key `source_uid` (ADR [0006](0006-cross-instance-migration.md)) is derived
   from `role` + `kind`/`group_kind` + identity-bearing config. Its stability across
   scheduling state changes must be guaranteed. A flat struct makes that guarantee
   conventional, not structural.
2. The role/kind discriminator invariant (ADR [0003](0003-group-sources.md)) must hold at
   construction time. Validating it on the same object that carries mutable scheduling
   fields conflates two concerns.

## Decision

Split `SourceRow` into two frozen dataclasses:

- `SourceIdentity` holds the immutable identity and configuration fields: `source_uid`,
  `name`, `role`, `kind`, `group_kind`, `config_json`, `parent_id`, `window_inherited`.
  Its `__post_init__` enforces the role/kind discriminator (source requires `kind`, group
  requires `group_kind`, each forbids the other).
- `SourceRow` wraps `identity: SourceIdentity` with the mutable lifecycle and scheduling
  fields: `enabled`, `state`, `access_state`, `cadence_kind`, `poll_interval_seconds`,
  `window_json`, timestamps, error tracking, and surrogate `id`.

`SourceRow` exposes the most commonly accessed identity fields (`source_uid`, `name`,
`role`, `kind`, `group_kind`, `parent_id`, `window_inherited`) as read-through `@property`
accessors so callers do not need to reach into `.identity` for routine operations.

## Consequences

- `source_uid` stability is guaranteed by construction: scheduling mutations produce a new
  `SourceRow` wrapping the same `SourceIdentity`, so the natural key never changes.
- Discriminator validation runs at `SourceIdentity` construction, before any scheduling
  fields are involved.
- Callers that only need identity (e.g. `compute_source_uid`, group expansion) accept
  `SourceIdentity` directly without carrying scheduling baggage.
- The `StorageBackend` ABC methods that return or accept `SourceRow` are unchanged; the
  property accessors preserve the flat access surface.
