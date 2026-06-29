# Decision records (ADRs)

Architecture decisions for the Herald collection layer, especially where the
implementation deviates from or extends the [foundation specification](../foundation).
Each ADR cites only the foundation documents as authority.

| ADR | Title |
|-----|-------|
| [0001-collection-subpackage.md](0001-collection-subpackage.md) | Collection layer nested under `herald/collection/` |
| [0002-window-range-model.md](0002-window-range-model.md) | Typed Window union for per-source collection ranges |
| [0003-group-sources.md](0003-group-sources.md) | Group sources as first-class parent rows with a `role` discriminator |
| [0004-source-state-candidate.md](0004-source-state-candidate.md) | `SourceState.candidate` to match the curation state machine |
| [0005-adapter-window-param.md](0005-adapter-window-param.md) | Adapter `poll(cursor, *, window=None)` |
| [0006-cross-instance-migration.md](0006-cross-instance-migration.md) | Cross-instance migration and the logical interchange contract |
| [0007-backfill-event-provenance.md](0007-backfill-event-provenance.md) | Backfill event provenance (`EventOrigin`) |
| [0008-carried-extensions.md](0008-carried-extensions.md) | `SourceKind` extension, cross-source identity, snapshot metrics, scheduling fields |
| [0009-source-identity-split.md](0009-source-identity-split.md) | `SourceRow`/`SourceIdentity` two-layer identity split |
| [0010-exception-hierarchy.md](0010-exception-hierarchy.md) | Typed exception hierarchy |
| [0011-person-observation-model.md](0011-person-observation-model.md) | Person observation model (two-phase identity resolution) |
