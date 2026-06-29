# 0010 - Typed exception hierarchy

**Status:** accepted

## Context

The collection layer spans several failure domains: the storage backend can fail (missing
blob, unknown source), the HTTP/network fetch layer can fail (robots disallowed, edge block,
auth required), and a source adapter can fail during polling (feasibility probe failure,
wire-format errors). The orchestrator, CLI, and downstream callers need to distinguish these
stages to set `access_state` correctly, decide whether to retry, and produce actionable
error messages.

The foundation spec ([1-collection.md](../foundation/1-collection.md)) describes
`access_state` values (`open`, `partial`, `blocked-by-robots`, `blocked-by-edge`,
`requires-signed-requests`) but does not prescribe how the implementation classifies errors
into those states. That mapping is an implementation decision.

## Decision

Define a three-branch exception taxonomy under `HeraldError`:

```
HeraldError
+-- StorageError
|   +-- BlobNotFoundError
|   +-- UnknownSourceError
+-- FetchError
|   +-- RobotsDisallowedError
|   +-- EdgeBlockError
|   +-- AuthRequiredError
+-- AdapterError
|   +-- FeasibilityError
+-- SourceConfigError
+-- CredentialError
```

The three branches correspond to distinct pipeline stages:

- **`StorageError`** - the backend operation itself failed (a missing blob is not a fetch
  failure; an unknown source id is not a config error).
- **`FetchError`** - the HTTP/network layer classified the failure. The orchestrator maps
  subclasses to `access_state`: `RobotsDisallowedError` to `blocked-by-robots`,
  `EdgeBlockError` to `blocked-by-edge`, `AuthRequiredError` to
  `requires-signed-requests`.
- **`AdapterError`** - the source adapter failed while polling. `FeasibilityError` is a
  runtime probe determining a source cannot be collected as configured, categorically
  different from a transient fetch failure.

`SourceConfigError` and `CredentialError` are configuration-time failures (before the
backend or network is ever used), kept as direct children of `HeraldError` rather than
under `StorageError`.

The CLI maps any `HeraldError` to `error: ...` on stderr with exit code 1.

## Consequences

- Callers catch at the appropriate granularity: the CLI catches `HeraldError` broadly, the
  orchestrator catches `FetchError` subclasses to set `access_state`, adapters raise
  `AdapterError` for polling failures.
- The `access_state` mapping is driven by exception type, not by inspecting status codes or
  error strings in caller code.
- New error conditions are added as subclasses of the appropriate branch without changing
  existing catch sites.
