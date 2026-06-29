# 0011 - Person observation model (two-phase identity resolution)

**Status:** accepted

## Context

[2-people.md](../foundation/2-people.md) defines the person-tracking schema: persons with
name variants, handles, affiliations, committee roles, and a watch/snapshot mechanism. The
collection layer's mechanical observer (no LLM) extracts person mentions from ingested
content, but not every mention can be resolved to a known `PersonRow`. A naive approach
(create a `PersonRow` immediately for every observed name) would populate the registry with
dirty, unresolved entries that downstream layers cannot trust.

## Decision

Adopt a two-phase identity resolution pattern:

1. **Observation phase.** When the mechanical observer encounters a name, handle, or email
   domain in extracted content that it cannot confidently resolve to an existing person, it
   creates a `PersonPendingCandidateRow` with `resolution_status = ResolutionStatus.PENDING`.
   The row captures the raw observation (`observed_name`, `observed_handles`,
   `observed_email_domain`, `observed_context`) plus provenance (`content_id`,
   `first_seen`, `last_seen`).

2. **Resolution phase.** A subsequent step (human review or automated matching via the
   intelligence layer) either links the candidate to an existing `PersonRow` (status
   `RESOLVED`) or discards it (status `REJECTED`). Only resolved candidates produce
   durable person records.

### Person natural key

`PersonRow.person_id` is a `str` natural key (e.g. `"wg21:bjarne-stroustrup"`), not a
surrogate integer. This is consistent with the cross-instance migration story (ADR
[0006](0006-cross-instance-migration.md)): `person_id` survives engine changes and
instance transfers without surrogate-key remapping.

### Person event vocabulary

`PersonEventKind` (`role_change` | `affiliation_change` | `publication` | `mention`)
enumerates the event types the mechanical observer and the intelligence layer can produce.
These are distinct from the seven `EventKind` collection events: person events are
per-person records, not outbox entries.

### Resolution status vocabulary

`ResolutionStatus` (`pending` | `resolved` | `rejected`) is the lifecycle of a
`PersonPendingCandidateRow`. The three values are exhaustive for the current model.

## Consequences

- No dirty person entries: the `persons` table contains only resolved, trustworthy records.
- Pending candidates are queryable and auditable, providing a backlog for human review.
- The string `person_id` natural key is stable across instances and engines.
- The observation/resolution split keeps the mechanical observer (collection, no LLM) cleanly
  separated from identity resolution (intelligence layer, possibly LLM-assisted).
- `PersonEventKind` and `ResolutionStatus` are stored as `StrEnum` values, following the
  same wire/storage contract discipline as all other collection-layer vocabularies.
