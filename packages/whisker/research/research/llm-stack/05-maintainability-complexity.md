# 05 - Maintainability-Complexity

**Verdict:** usable-with-conditions — the advisory lane ships and persists sidecars, but dead cascade wiring, a 768-LOC backend god-module with four near-copy pydantic-ai paths, and cross-package private imports are structural debt that will mislead the next maintainer about what actually runs in production.
**Confidence:** high

## Findings
- [CRITICAL] The two-tier cascade is dead code in production: `escalated=true` in **0 / 197** sidecars (00-baseline:46). The Python gate at `adjudicate.py:206-208` (`CONFIDENCE_AMBIGUOUS_LO`..`CONFIDENCE_AMBIGUOUS_HI`, `constants.py:22-23`) never fired because tier1 confidence never landed in `[0.35, 0.65]`. Compounding rot: `fast` and `deep` both bind to `alliance-pod` (`tapetum_llm.md:17-19`), so even a triggered escalation would be a second pass on the same model, not a larger one. Step `"2. Adjudicate"` (`adjudicate.py:284`, hooks at `:275-286`) is exercised only in unit tests (`test_tapetum_llm.py:277-303`), not in the 200-paper batch.
  Impact: maintainers will "fix" tier2 thresholds or prompts believing a cascade exists; production behavior is single-tier triage only, contradicting the authority doc (`tapetum_llm.md:3`, `:10`).

- [HIGH] `model_backends.py` (768 LOC, 00-baseline:24) carries four pydantic-ai `Agent.run()` implementations that are copy-paste variants: `VllmThinkingBackend._run_with_tools` (`model_backends.py:427-490`), `Llama3Backend.run` (`:525-583`), `Qwen3Backend.run` (`:617-678`), `AnthropicBackend.run` (`:707-756`). Each repeats the same skeleton: lazy pydantic-ai imports, `ModelSettings(temperature=0.0, parallel_tool_calls=False, ...)`, `Agent(..., retries=3)`, tool registration loop, `UsageLimits(request_limit=...)`, `UsageLimitExceeded` handler with `exc.add_note`, and `render_debug_md` append. Only Qwen3 adds `extra_body`; Anthropic omits `top_p`/`seed`.
  Impact: a sampling-pin or retry-policy change (D2/D10) must be edited in four places; one backend will drift (already visible in Anthropic omitting `top_p=1.0, seed=0` at `:725-728` vs Llama3 at `:550-555`).

- [HIGH] `_PipelineState._result` is a dynamic attribute hack, not a dataclass field (`adjudicate.py:272` `state._result = result  # type: ignore[attr-defined]`; read back via `getattr(state, "_result", None)` at `:427`). The dataclass already declares `tier1`, `tier2`, `chunked`, `partial` (`:136-149`) but omits the one value the entry point needs.
  Impact: mypy is silenced instead of enforced; refactors to `_PipelineState` will not surface missing-result bugs at type-check time; the fallback stub at `:428-438` masks silent pipeline failures as `"pipeline did not produce a result"`.

- [MED] Cross-module private coupling: `tapetum_llm/cli.py:30` imports `whisker.__main__._render_progress`, a module-private helper defined at `whisker/__main__.py:90`. The tapetum batch bar hard-codes the `"whisker [...]"` prefix inside that function (`__main__.py:107`), so tapetum batch UX is tied to whisker CLI internals, not a shared utility.
  Impact: renaming, moving, or changing `_render_progress` in whisker breaks tapetum batch mode with no compile-time signal; the correct fix (extract to `whisker/progress.py` or duplicate a 20-line helper) is obvious but unimplemented.

- [MED] `services.py` (526 LOC, 00-baseline:25) is a loader god-module: four public loaders (`load_services`, `load_classifiers`, `load_embedders`, `load_transformer_providers`) each independently call `_find_services_toml()` (`:87-94`) and `open(path, "rb")` + `tomllib.load` (`:128-136`, `:251-259`, `:314-322`, `:365-373`). Docstrings still reference `resolve_slots` (`:410-411`, `:434-435`) which no longer exists in this file (only `resolve_pipeline_models` at `:462`).
  Impact: a caller loading multiple resource types re-parses SERVICES.toml N times; stale doc references send new pipeline authors to a missing symbol.

- [MED] `_BATCH_QUIET_LOGGERS` in `cli.py:43-48` names loggers from other packages (`"pipeline.runner"`, `"pipeline.services"`, `"httpx"`, `"openai"`). Batch mode mutates their levels at runtime (`cli.py:252-253`).
  Impact: whisker tapetum CLI is coupled to pipeline module naming; a logger rename in pipeline silently restores per-paper log spam or hides new diagnostic channels.

- [LOW] Chunked oversize papers permanently skip tier2 with a deferred comment (`adjudicate.py:200-204` "Tier2 escalation for chunked papers is a later upgrade"). Test coverage confirms skip behavior (`test_tapetum_llm.py:710-743`) but not how many production papers hit this branch.
  Impact: a second dead escalation sub-path alongside the 0/197 global stat; maintainers cannot tell from runtime metrics whether chunking or calibration killed tier2.

## False-pass hypothesis
With tier2 never running (0/197 escalated), every paper gets a single triage pass whose self-reported confidence exits the ambiguous band (`adjudicate.py:206-208`). An overconfident tier1 (`confidence > 0.65`) on a token-preserving semantic defect would stand unchallenged — the dead cascade removes the designed second opinion.

## False-fail hypothesis
none found — maintainability findings describe dead or duplicated structure, not verdict skew. (Over-review at 106/197 is a calibration concern for persona 21, not a coupling defect.)

## What would change my mind
A reproduced batch run (or labeled eval set) showing `escalated=true` in a non-trivial fraction of sidecars **with `fast` and `deep` bound to distinct services**, proving the cascade path is live and worth the step-2 maintenance cost.
