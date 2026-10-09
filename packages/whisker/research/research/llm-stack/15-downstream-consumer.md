# 15 - Downstream-Consumer

**Verdict:** usable-with-conditions — the framework runs real pipelines (agora, assay, tapetum), but a new author must reverse-engineer three existing packages to learn which authority-doc fields are live vs decorative; several parsed metadata fields silently do nothing at runtime.
**Confidence:** high

## Findings

- [CRITICAL] Per-step `**max-output:**` and `**thinking-budget:**` parse cleanly into `StepPrompt` but `run_agent` never forwards them to `AgentBackend.run`, so every LLM call uses construction-time defaults regardless of the authority doc. Evidence: parsed at `prompt.py:108-115`, `:389-390`; `AgentBackend.run` docstring claims "Per-step overrides come from StepMeta.max_output_tokens via the runner" at `agents.py:127-133`; actual call at `runner.py:266-272` passes only `tools`, `label`, `debug_log`, `request_limit`. Impact: trap #1 from `00-baseline.md`; author tunes budgets in markdown, sees no error, gets wrong token/thinking behavior and non-reproducible cost/latency vs their design doc.

- [HIGH] Three authority-doc control planes are parsed but never consumed by `dispatch`: `**Execution:**` (`prompt.py:93-94`, `:366`), `**Condition:**` (`prompt.py:99-100`, `:386`), and `**concurrency:**` / `## Config` concurrency (`prompt.py:121-123`, `:211-212`, `:392`; `runner.py:106`). Runner only honors `hooks.custom`, `hooks.parallel`, and `hooks.guard` (`runner.py:356-384`). Agora duplicates condition logic: markdown declares `**Condition:** encounter_count > 0` (`agora.md:330`) while skip behavior lives in Python `hooks.guard` (`agora/pipeline.py:692`, `:127-129`). Impact: author declaring `**Execution:** subagent` or `**Condition:** ...` believes the framework enforces it; nothing happens until they write duplicate Python.

- [HIGH] D11 "per-package concurrency opt-in" has no discoverable wiring from authority doc to runtime. `pipeline/CLAUDE.md:89` documents `_parallel_semaphore` in `runner.py`, but no such symbol exists (grep confirms only `_task_semaphore` at `tasks.py:38`). `StepContext.gather_concurrent` (`runner.py:133-162`) is the ordered primitive, and `default_concurrency` on `StepContext` (`runner.py:106`) is never set by the framework; `tapetum_llm.md:23` `**concurrency:** 1` is inert. Impact: author reads D11, searches for semaphore knobs, finds a dead doc reference; raising global semaphores is forbidden (`tasks.py:30-36`, `MODELS.md` via baseline); the only safe path is custom-hook batch fan-out outside `dispatch`, undiscoverable from exports alone.

- [HIGH] Hook dict keys must exactly match the H2 section header string, not the numeric step alone. `build_pipeline` pairs `hooks[s.name]` where `name` is the full section key (`prompt.py:499-518`, `:280-282`); `_STEP_RE` accepts both `"Step 1 - Foo"` and `"1. Foo"` (`prompt.py:43`, `:344-348`). Assay keys hooks as `"7. Collect"` (`assay/CLAUDE.md` invariant); agora uses `"Step 0 - Load"`. Impact: walkthrough stumble at step 2 — author writes `hooks={"1. Analyze": ...}` against `## Step 1 - Analyze` and gets `HookMismatchError` listing sorted orphan/missing names (`prompt.py:504-513`) with no hint about header-string convention.

- [MED] `validate_capabilities` is documented as mandatory after `build_pipeline` (`validate.py:10-11`, `pipeline/CLAUDE.md:13`) but is not part of `build_pipeline` and is skipped by agora (`agora/pipeline.py:748-796` has no call; assay calls it at `assay/pipeline.py:1868`). Tool/thinking mismatches surface at runtime as `NotImplementedError` from `AgentBackend.run` (`agents.py:144-148`) instead of the construction-time table (`validate.py:160-185`). Impact: 3-step pipeline with `**Tools:** read_paper` on a non-tools backend passes `build_pipeline`, fails mid-run on step 1 with a weaker message than `CapabilityMismatchError`.

- [MED] Tool-enabled LLM steps require manual two-layer wiring with no framework helper. Authority doc declares names via `**Tools:**` (`prompt.py:385`); `run_agent` resolves them from `ctx.tool_registry` (`runner.py:251-259`), raising `HookMismatchError` if missing (`runner.py:255-258`). `make_read_paper_tool` is exported (`__init__.py:92-93`, `:114`) but the author must bind it under the exact string name in a custom entry function (agora pattern at `agora/pipeline.py:773-786`). Impact: walkthrough stumble at step 1 — parse succeeds, first LLM call fails with "declares tool 'read_paper' but no callable is registered".

- [LOW] Malformed numeric step metadata bypasses the `PromptFileError` hierarchy. `_opt_int` uses bare `int(raw)` (`prompt.py:371-372`, `:389-392`); `**max-output:** not-a-number` raises `ValueError`, not `PromptFileError`/`MissingMetadataError`, despite `errors.py:43-48` promising structural prompt errors name the expected format. Impact: typo in authority doc yields an uncategorized stack trace instead of "edit the prompt file".

## False-pass hypothesis

Author ships a 3-step pipeline whose authority doc declares per-step `**max-output:** 2048` / `**thinking-budget:** 1024`, passes `build_pipeline` and a smoke test, and believes budgets are live because `parse_step_prompt` tests green and debug comments show `max_tokens=4096` from agent construction — never noticing the runner ignores step fields (`runner.py:266-272`). Production runs at 4096/no-thinking until a truncation or cost incident; no test in `packages/pipeline/tests/` asserts step-budget forwarding.

## False-fail hypothesis

Author copies agora's `**Condition:**` bullet into their markdown expecting framework skip semantics; without a matching `hooks.guard`, the step always runs. If their step assumes skipped-when-empty state, they get validation errors or garbage output and blame the LLM backend rather than the decorative metadata (`prompt.py:386` vs `runner.py:337-339` guard hook only).

## What would change my mind

A single integration test or runtime assertion in `run_agent` that forwards `spec.step.max_output_tokens` and `spec.step.thinking_budget` when non-None (or raises `PromptFileError` at `build_pipeline` if those fields are set but forwarding is disabled), plus a one-page "new pipeline checklist" listing live vs parsed-only authority-doc fields.
