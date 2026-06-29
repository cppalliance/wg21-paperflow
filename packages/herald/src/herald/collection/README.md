# Herald collection layer

The pure-Python, no-LLM ingestion engine. One layer of the Herald system; the others
(intelligence, writer, editorial) will land as sibling subpackages under `herald.`.

- Spec: [`1-collection.md`](../../../docs/foundation/1-collection.md)
- ADRs: [`docs/decisions`](../../../docs/decisions)
- Agent rules: [`CLAUDE.md`](CLAUDE.md)
- Onboarding: [`docs/onboarding`](../../../docs/onboarding)

## Status

Types + contracts + skeleton. Backends, adapters, the orchestrator body, scheduler, and
registry land in later milestones without changing these types.

## Layout

```
herald/collection/
  enums.py  records.py  errors.py     contract vocabulary + frozen types + exceptions
  orchestrator.py                     run_sweep (composition point)
  storage/  events/  change/  normalize/  fetch/  extract/
  dedup/    sources/ persons/ schedule/ registry/ obs/
```

## The nine-component pipeline

source adapter, normalize, fetch, change detection, extract, dedup, person observation,
record (transactional outbox), consume. See
[`overview.md`](../../../docs/onboarding/overview.md) for details.
