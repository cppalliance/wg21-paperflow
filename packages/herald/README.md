# herald

The C++ ecosystem ingestion + generation pipeline. Herald is a multi-layer system - a
collection layer, people tracking, intelligence, and a writer/editorial/research-desk layer
(see [`docs/foundation`](docs/foundation)). Each layer is a subpackage under `herald.`.

The first implemented layer is the **collection layer**, under
[`src/herald/collection`](src/herald/collection) - its README documents what it does, its
status, and its layout. The top-level `herald` package is a thin namespace so sibling layers
(intelligence, writer, editorial) can be added later.

- Specification of record: [`docs/foundation`](docs/foundation)
- Design decisions / deviations: [`docs/decisions`](docs/decisions)
- Getting started: [`docs/onboarding`](docs/onboarding)

## Development

This package is a member of the `wg21-paperflow` uv workspace; tool config (ruff, pyright,
pytest) is owned by the workspace root.

```bash
# from the workspace root (d:/_Cpp_Alliance/wg21.org/wg21-paperflow)
uv sync --all-packages
uv run pytest packages/herald/tests
uv run ruff check packages/herald
uv run pyright packages/herald/src
```

The CLI entry point is `herald` (`herald --help`).
