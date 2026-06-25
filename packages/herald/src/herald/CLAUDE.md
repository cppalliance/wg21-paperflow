# herald - Agent Rules

## What this is

Herald is the C++ ecosystem ingestion + generation pipeline: it continuously ingests
everything relevant to C++ (public and private), tracks the people involved, and generates
publishable article drafts for a human editor to curate. It is a **multi-layer system** -
each layer is (or will be) a subpackage under `herald.`. The authoritative specification for
every layer lives in [`docs/foundation`](../../docs/foundation); design deviations are
recorded in [`docs/decisions`](../../docs/decisions).

Only the **collection layer** is implemented today. The other layers are specified in the
foundation docs and added later as sibling subpackages. This file holds the **package-wide**
and **cross-layer** rules; each layer keeps its own `CLAUDE.md` for layer-specific invariants.

## Layers

| Layer | Subpackage | Status | Spec |
|-------|------------|--------|------|
| Collection | `herald.collection` | implemented (types + contracts + skeleton) | [1-collection.md](../../docs/foundation/1-collection.md) |
| Intelligence (identity resolution, topics, evidence) | planned | planned | [residue.md](../../docs/foundation/residue.md) |
| Writer (+ research desk) | planned | planned | [3-writer.md](../../docs/foundation/3-writer.md), [story-shapes.md](../../docs/foundation/story-shapes.md), [register-lock.md](../../docs/foundation/register-lock.md) |
| Editorial (+ source curation) | planned | planned | [residue.md](../../docs/foundation/residue.md) |
| People tracking | woven across collection / intelligence / writer | planned | [2-people.md](../../docs/foundation/2-people.md) |
| wg21.org integration (Django/Postgres) | separate wg21.org repo | external | [residue.md](../../docs/foundation/residue.md) |

Path note: subpackage names beyond `herald.collection` are indicative; follow the foundation
docs when those layers land.

## Package layout invariants

- Each layer is confined to its own subpackage under `herald/` (the collection layer is
  `herald/collection/`). The top-level `herald` package stays a thin namespace
  (`__version__`, `__all__`); `import herald` must stay cheap - no heavy optional deps at
  import time (subpackages lazy-import their transports/models).
- Documentation lives under `packages/herald/docs/`: `foundation/` (the spec of record),
  `decisions/` (ADRs), `onboarding/`, `todo/`. Every subpackage/layer carries its own
  `CLAUDE.md`; put layer-specific invariants there, not here.
- Sibling packaging conventions are non-negotiable: hatchling + `src/` layout, no per-package
  ruff/pytest/pyright config (the workspace root owns those), the standard BSL-1.0 copyright
  header on every `.py` (naming the file's copyright holder - its author or the C++ Alliance;
  copy the format from an existing file), a `py.typed` marker.
- **Depend on less.** Each subsystem pulls in exactly what it needs and no framework; Django
  belongs to wg21.org, not here. The `StorageBackend` ABC is the seam that lets every layer
  depend on plain Python instead of a database engine.

## Cross-layer invariants

- **The `collection_events` outbox is the contract between collection and everything
  downstream.** Downstream layers consume it by cursor (a `consumer_cursors` row + a
  `process(event)` fn); delivery is at-least-once, so consumers must be idempotent. The seven
  `EventKind`s are fixed - new semantics are payload annotations, not new kinds.
- **No LLM in collection or in mechanical person observation.** Those stay classical Python.
  Every LLM call (intelligence, writer, editorial, the Feed Proposer, prose refresh) goes
  through the `pipeline` package against the self-hosted model fleet - never a cloud API.
- **Backfill provenance, not suppression.** Backfilled historical content is emitted with
  `EventOrigin.BACKFILL`; generation-driving consumers (writer catalog/triage, intelligence
  topics) ignore it, archival/enhancement consumers (research desk, fine-tune export,
  dossiers) process all origins. The consumer matrix lives in
  [`collection/CLAUDE.md`](collection/CLAUDE.md).
- **`visibility` is load-bearing across layers.** Content carries `public`/`private`/
  `restricted` from ingestion; collection never gates on it, but the writer and the fine-tune
  export must respect it when deciding what to quote, publish, or train on.
- **One contract, two backends.** `StorageBackend` is ORM-agnostic: `SqliteBackend` for
  local/dev, a Postgres/Django backend for production (shared with wg21.org). R2 is shared too
  (Herald via `fsspec`, Django via `django-storages`), namespaced by prefix. New persistence
  is added to the ABC first.

## Where to look

- Collection-layer rules + the `collection_events` consumer matrix:
  [`collection/CLAUDE.md`](collection/CLAUDE.md).
- Subpackage rules: `collection/storage/CLAUDE.md`, `collection/sources/CLAUDE.md` (a
  subpackage gains its own `CLAUDE.md` once its contract or code lands in the tree).
- Getting started: [`docs/onboarding`](../../docs/onboarding).
