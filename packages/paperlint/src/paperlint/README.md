# paperlint

The LLM pipeline that finds mechanically verifiable defects in WG21 C++ standards papers. Misspelled identifiers, broken cross-references, code samples that don't match their prose, contradictions. PaperLint points at things; the committee decides the rest.

User-facing CLI documentation lives in the [root README](../../../../README.md). This file documents the paperlint package itself for contributors. The CLI binary is `paperflow`, not `paperlint`.

## Pipeline

`paperlint.orchestrator.run_paper_eval` is the per-paper entry point. It loads `<pid>.md` and `<pid>.meta.json` via the storage backend (no fetch, no tomd), then runs:

1. `step_discovery` (LLM, multi-pass) -> `<pid>.1-findings.json`
2. `step_verify_quotes` (pure Python; for each evidence quote, first tries a literal substring match against the paper markdown, falling back to a whitespace-normalized match. Findings with any unverifiable evidence are dropped before the gate sees them.)
3. `step_gate` (LLM) -> `<pid>.2-gate.json`
4. `step_suppress_known_fps` -> `<pid>.2c-suppressed.json`
5. `step_summary_writer` (LLM) -> assembled into `<pid>.eval.json`

See `CLAUDE.md` in this directory for invariants and the LLM contract.

## Models

Defaults set in `paperlint/llm.py`:

- Discovery + Gate: `anthropic/claude-opus-4.7`, JSON mode, extended thinking enabled.
- Summary: `anthropic/claude-sonnet-4.6`, JSON mode, no thinking.

Override either at process start with `PAPERLINT_DISCOVERY_MODEL` or `PAPERLINT_SUMMARY_MODEL`. Routing is OpenRouter via the `openai` SDK.

## Environment

- `OPENROUTER_API_KEY` (required for `eval` / `full`; loaded from `.env` / `.env.local` automatically).
- `PAPERLINT_DISCOVERY_MODEL` - override the OpenRouter slug for the discovery and gate stages.
- `PAPERLINT_SUMMARY_MODEL` - override the OpenRouter slug for the summary stage.
- `PAPERLINT_LOG_FILE=/path/to/log` - append structured logs there.
- `PAPERLINT_LOG_TO_WORKSPACE=1` - append to `<workspace>/paperlint.log` instead.
- `PAPERLINT_ERROR_TRACEBACK=1` - embed tracebacks in `<pid>.eval.json` on partial runs.

## Tests

```
uv run pytest packages/paperlint/tests
```

Tests are hermetic: LLM calls are stubbed at `paperlint.llm.call_with_retry` / `build_client`. Don't add tests that hit OpenRouter.
