# 0003 - Group sources as first-class parent rows with a `role` discriminator

**Status:** accepted

## Context

[1-collection.md](../foundation/1-collection.md) defines a source as something an adapter
*polls* to produce a stream of fetch candidates, and stresses that "adding another reflector
or another MCP index does not touch the rest of the system." But several real sources are
containers, not pollables: a GitHub org with hundreds of submodule repos, a reflector host
with many lists, a Discord guild with many channels. Registering each child by hand is the
exact friction the collection layer is meant to remove, and putting `github_org` into the
pollable `SourceKind` vocabulary would break the source -> candidate abstraction (you cannot
`poll` an org into content the way you poll a repo).

## Decision

Model groups as first-class **registry rows** distinguished by `SourceRow.role`:

- `role=source` rows carry a `SourceKind` and are pollable.
- `role=group` rows carry a `GroupKind` (`github_org` / `reflector_host` / `discord_guild`),
  kept in a separate enum so `SourceKind` stays the clean pollable set. A later discovery
  step (separate from `poll`) expands a group into child `role=source` rows linked by
  `parent_id`; subset selection lives in the group's `config_json`.
- `window_inherited` lets a child resolve its window from the parent, composing ranges x groups.

New children land as `candidate`/`pending` for curation
([residue.md](../foundation/residue.md)); vanished children are demoted.

## Consequences

- "Register the org, pick a subset" works without polluting the adapter vocabulary.
- Group expansion is a discovery concern, not a `poll` concern; adapters stay pure producers.
- Expansion logic itself is deferred; this PR lands only the data-model fields.
