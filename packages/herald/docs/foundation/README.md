# Herald foundation documents

The **authoritative specification** for Herald - the single source of truth for its intent
and architecture. Implementation decisions that deviate from these documents are recorded in
[../decisions](../decisions).

| File | Covers |
|------|--------|
| [1-collection.md](1-collection.md) | The collection layer: the nine-component pipeline, the `collection_events` outbox, the data model, change detection, person observation, tooling, bot etiquette. |
| [2-people.md](2-people.md) | People tracking: identity resolution, the person/dossier data model, the collection-vs-intelligence-vs-writer boundary. |
| [3-writer.md](3-writer.md) | Article generation: the daily catalog, shape triage, briefs, drafts, the research desk, journalist personas. |
| [story-shapes.md](story-shapes.md) | The article-shape inventory. |
| [register-lock.md](register-lock.md) | The writer's locked analytical register (emergent, not performed). |
| [residue.md](residue.md) | Design material for the downstream layers (intelligence, source curation, writer, editorial) and the shared-Postgres integration with wg21.org. |
