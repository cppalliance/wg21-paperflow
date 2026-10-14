# 04 - API-Contract-Design

**Verdict:** usable-with-conditions   The parser and `AgentBackend.run` API are sound, but the framework-managed path (`run_agent` / `dispatch`) silently drops authority-doc step budgets that docstrings promise the runner forwards; tapetum relies on that path, so declared `max-output` / `thinking-budget` are fiction until wired.
**Confidence:** high

## Findings

- [CRITICAL] Per-step `max-output` and `thinking-budget` are parsed from the authority doc but never forwarded by `run_agent`. Evidence: `tapetum_llm.md:118-119` (Triage `2048` / `1024`), `tapetum_llm.md:137-139` (Adjudicate `4096` / `4096`); `prompt.py:389-390` maps bullets to `StepPrompt.max_output_tokens` / `thinking_budget`; `agents.py:127-133` docstring claims "Per-step overrides come from … via the runner"; `runner.py:266-272` calls `agent.run(...)` with only `tools`, `label`, `debug_log`, `request_limit` (no `max_tokens` / `thinking_budget`); tapetum custom hooks call `run_agent` directly (`adjudicate.py:181`, `:191`, `:211`). Impact: every tapetum LLM call runs at construction-time `max_tokens=4096` (`adjudicate.py:391`) with `thinking_budget=None` (thinking off per `model_backends.py:305-309`), not the authority-doc budgets. Fix shape: in `run_agent`, forward `spec.step` meta into `agent.run`:

  ```python
  max_tokens=spec.step.max_output_tokens,
  thinking_budget=spec.step.thinking_budget,
  ```

  `AgentBackend.run` already resolves `None` to construction defaults (`agents.py:149-150`).

- [HIGH] `validate_capabilities` gates `agent.thinking_budget` at construction, not `spec.step.thinking_budget`. Evidence: `validate.py:74-76` docstring names "assigned `thinking_budget`"; check at `validate.py:121-128` reads `agent.thinking_budget` only; per-step `thinking_budget` on `StepPrompt` (`prompt.py:112-115`) is never validated. Impact: a pipeline can declare `**thinking-budget:** 4096` on a non-`thinking_capable` backend and pass construction-time validation while the declaration is both unenforced and (today) unapplied. Fix shape: extend `validate_capabilities` to also check `spec.step.thinking_budget` against `agent.thinking_capable` (treat `0` as disable, mirroring `test_validate_thinking_budget_zero_does_not_require_thinking_capable` at `test_capability_validation.py:313-318`).

- [HIGH] `## Config` `concurrency` is parsed but tapetum ignores it. Evidence: `tapetum_llm.md:23` declares `concurrency: 1`; `prompt.py:209-211` stores `PipelinePrompt.config`; `adjudicate.py:409` hardcodes `default_concurrency=1` instead of reading `prompt.config` (contrast assay: `pipeline.py:1854`, `:1885`). Impact: editing the authority doc's global concurrency knob has no effect on tapetum; future `--concurrency N` wiring must not assume the doc already drives behavior. Fix shape: `default_concurrency=int(prompt.config.get("concurrency", "1") or 1)` in `adjudicate_paper`, matching assay.

- [HIGH] Framework `dispatch` parallel mode ignores `spec.step.concurrency` and runs fan-out serially. Evidence: `StepPrompt.concurrency` parsed at `prompt.py:121-123`, `:392`; `StepContext.gather_concurrent` exists at `runner.py:133-162`; but `dispatch` parallel branch uses a plain `for msg in user_msgs: await run_agent(...)` (`runner.py:368-373`) and the docstring admits "sequentially" (`runner.py:298-299`). Impact: any pipeline using `hooks.parallel=True` without a custom hook (assay bypasses this by using `custom` hooks) cannot honor per-step concurrency from the authority doc. Fix shape: replace the serial loop with `gather_concurrent` keyed on `spec.step.concurrency or ctx.default_concurrency`.

- [MED] `run_task` omits the same per-call budget overrides. Evidence: `tasks.py:58-65` calls `agent.run(...)` without `max_tokens` / `thinking_budget`; no parameters exist on `run_task` (`tasks.py:41-50`). Impact: sub-agent fan-out paths cannot inherit step budgets even after `run_agent` is fixed unless callers thread overrides manually (assay pattern). Fix shape: add optional `max_tokens` / `thinking_budget` kwargs to `run_task` and forward them.

- [MED] Docstrings reference a phantom `StepMeta` type; the public type is `StepPrompt`. Evidence: `agents.py:128`, `:133` cite `StepMeta.max_output_tokens` / `thinking_budget`; `pipeline/CLAUDE.md:12`, `:34` export list names `StepMeta`; public re-export is `StepPrompt` only (`__init__.py:43`, `:156`); dataclass lives at `prompt.py:74-79`. Impact: downstream pipeline authors grep for `StepMeta`, find nothing, and may miss that budgets live on `spec.step`. Fix shape: rename references to `StepPrompt` (or add a deprecated alias).

- [MED] tapetum never calls `validate_capabilities` at pipeline construction. Evidence: `adjudicate.py:398-418` builds agents and dispatches with no validation call (contrast `assay/pipeline.py:1868`). Impact: logical-model typos or tool/thinking capability mismatches fail at runtime or silently, not at load time. Fix shape: `validate_capabilities(pipeline, prompt, agents)` before `dispatch`, matching assay.

- [LOW] `chunk-tokens` is parsed into `StepPrompt.chunk_tokens` (`prompt.py:117-119`, `:391`) but tapetum chunks by `MAX_PAPER_MD_CHARS` in Python (`adjudicate.py:178`, `chunking.py`) with no authority-doc hook. Impact: low for tapetum today (no `chunk-tokens` bullet in `tapetum_llm.md`), but the field is part of the advertised step-meta contract and is dead for any pipeline that expects the runner to honor it without custom hooks (assay reads it manually at `pipeline.py:524`).

## False-pass hypothesis

Triage runs with `thinking_budget=None` (thinking disabled, `model_backends.py:305-309`) and `max_tokens=4096` instead of the declared `2048`/`1024`. On DeepSeek-V4-Pro, reasoning models without `enable_thinking` / `thinking_token_budget` can emit overconfident structured JSON (baseline: 0 / 197 sidecars escalated, `00-baseline.md:46`; vLLM docs in `05-web.md:14` require explicit thinking enablement). A borderline table corruption gets `confidence=0.98`, exits the ambiguous band (`adjudicate.py:206-208`), never reaches Adjudicate step 2, and the lane records a false `pass`.

## False-fail hypothesis

Oversized-paper triage fires one `run_agent` call per H2 chunk serially (`adjudicate.py:187-191`) at `max_tokens=4096` per chunk instead of the declared `2048`. A chunk near the context ceiling truncates mid-JSON; the backend retries and may eventually fail with "Raw JSON completion failed" (`00-baseline.md:49`, `model_backends.py:76-85`), demoting a faithful conversion to a hard batch failure (3-sidecar gap) that a correctly budgeted triage call might have survived.

## What would change my mind

A debug transcript from a tapetum run where the `<!-- call: … | max_tokens=2048 -->` header (`agents.py:154-157`) shows Triage at `2048` and the vLLM request carries `thinking_token_budget=1024` in `extra_body` (`model_backends.py:309`). That would prove the runner forwards step meta end-to-end; grep of current `*.debug.tapetum_llm.md` artifacts showing `max_tokens=4096` on Triage would confirm the gap is live in production.
