# 0001 - Collection layer nested under `herald/collection/`

**Status:** accepted

## Context

The foundation describes Herald as a multi-layer system: a collection layer
([1-collection.md](../foundation/1-collection.md)), people tracking
([2-people.md](../foundation/2-people.md)), and a writer/editorial/research-desk layer
([3-writer.md](../foundation/3-writer.md), [residue.md](../foundation/residue.md)).
Only the collection layer is built first. A flat layout (`herald/storage/`, `herald/sources/`,
... directly under `herald/`) would imply the whole package *is* the collection layer and
would collide with the sibling layers when they arrive.

## Decision

Confine the collection layer to `herald/collection/`. Keep the top-level `herald` package a
thin namespace (`__version__`, `__all__`). Future layers become `herald/intelligence/`,
`herald/writer/`, etc.

## Consequences

- Import surface is `herald.collection.records`, `herald.collection.storage`, ...
- The package can host the other foundation layers later without moving collection code.
- A small extra path segment on every import, accepted for the structural clarity.
