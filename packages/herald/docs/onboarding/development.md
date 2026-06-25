# Development

`herald` is a member of the `wg21-paperflow` uv workspace. Tooling (ruff, pyright, pytest)
is configured once at the workspace root - this package adds no per-package tool config.

## Setup

```bash
# from the workspace root
uv sync --all-packages
```

## The loop

```bash
uv run pytest packages/herald/tests      # tests (network tests are deselected by default)
uv run ruff check packages/herald        # lint
uv run pyright packages/herald/src       # type-check
uv run herald --help                     # the CLI
```

CI runs the same checks on Ubuntu and Windows (`.github/workflows/tests.yml`): a ruff job, a
pyright job, and a per-package test matrix that includes `herald`.

## Conventions (inherited from the workspace)

- **Packaging:** hatchling + `src/` layout, a `py.typed` marker, and the standard BSL-1.0
  copyright header on every `.py` (name the file's copyright holder - its author or the
  C++ Alliance; copy the exact format from an existing file).
- **Types:** frozen `@dataclass` rows, `StrEnum` for any value that is stored or sent on the
  wire, typed unions (`Cursor`, `Window`, `Candidate`) with tagged-JSON codecs.
- **Depend on less:** the collection layer pulls in exactly what each subsystem needs and no
  framework. `import herald` stays cheap - heavy transports/extractors are lazy-imported by
  the subpackage that uses them.
- **The seams are sacred:** adapters are pure producers; `StorageBackend.record_item` is the
  only durable-commit point (keyword-only inputs); the seven event kinds are fixed (new
  semantics are payload fields). See the package and subpackage `CLAUDE.md` files.

## Where to add things

- **A new source type:** a new adapter module under `collection/sources/`, a `SourceKind`
  value, and a registry config schema. No orchestrator edits.
- **A new event semantic:** a payload field, not a new `EventKind`.
- **A new persisted field:** the frozen row in `records.py`, then the backend(s).

Read [overview.md](overview.md) first, then the relevant `CLAUDE.md`, then
[../decisions](../decisions) for why the model looks the way it does.
