# herald

C++ ecosystem ingestion + generation pipeline. Collection, people tracking, intelligence,
writer, and editorial, each a subpackage under `herald.`. Only the collection layer is built
today; the rest is specified in [`docs/foundation`](docs/foundation) and will land as sibling
subpackages.

- Spec: [`docs/foundation`](docs/foundation)
- ADRs: [`docs/decisions`](docs/decisions)
- Onboarding: [`docs/onboarding`](docs/onboarding)

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
