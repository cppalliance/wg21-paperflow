# 0004 - `SourceState.candidate` to match the curation lifecycle

**Status:** accepted

## Context

The `sources` table in [1-collection.md](../foundation/1-collection.md) carries only an
`enabled` boolean. The source-curation design in
[residue.md](../foundation/residue.md) describes a richer
lifecycle: a source is first *observed* as a candidate (e.g. harvested from outbound links),
then *pending* review, then promoted to *active* or *rejected*, and *demoted* if it goes
dark or turns hostile (1-collection.md's "graceful tier-down" records a block and demotes).

## Decision

Model the lifecycle explicitly as `SourceState` = `candidate -> pending -> active /
rejected / demoted`, alongside the spec's `enabled` flag (which remains an operational
on/off independent of curation state).

## Consequences

- The candidate harvester can insert `candidate` rows that never get polled until promoted.
- `enabled` and `state` are orthogonal: an `active` source can be temporarily `enabled=false`.
- A small enum addition; no change to the seven event kinds or the adapter contract.
