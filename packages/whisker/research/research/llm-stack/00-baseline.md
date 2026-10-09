# llm-stack - Evidence Baseline (Step 0)

**Target:** our own LLM stack, red-teamed as a self-target (comparison codebase = the same monorepo; adopt/replace axis becomes **keep / redesign / harden**).
**Repo:** `c:\Users\sabo2\Desktop\cppalliance` @ HEAD `e66116a09bbe833a8080e9e60a95833ab339cf64` (2026-07-03).
**Slug:** `llm-stack`. **Prior work:** none (first run; no `packages/whisker/research/llm-stack/SYNTHESIS.md`, no `_index.md`).

Every claim below carries a `file:line` or a reproduced runtime number. Later personas MUST argue against these anchors, not against guesses.

---

## What the target is

Two layers of one LLM pipeline:

1. **`packages/pipeline/src/pipeline/`** - a model-family-agnostic LLM pipeline framework. `model_backends.py` holds one `ModelBackend` subclass per model family (`VllmThinkingBackend`, `Llama3Backend`, `Qwen3Backend`, `AnthropicBackend`) plus a `BACKEND_REGISTRY` (`model_backends.py:763-768`). `runner.py` drives step execution (`dispatch`), the framework-managed LLM caller (`run_agent`), and `StepContext`. `agents.py` wraps a backend with per-call config (`AgentBackend`). `services.py` parses `SERVICES.toml` into a frozen `ServiceRegistry` and resolves logical slots. `tools.py` is the prompt-injection defense (`inject_untrusted`, `escape_guard_delimiters`, `guard_instruction`) and the scoped `read_paper` tool. `prompt.py` parses a pipeline's markdown authority doc into `PipelinePrompt` / `StepPrompt` / `StepSpec`.
2. **`packages/whisker/src/whisker/tapetum_llm/`** - an advisory conversion-fidelity lane built on the framework. `adjudicate.py` runs a two-tier cascade (fast triage -> deep adjudicate, gated in Python) plus `select_candidates` (pure-Python candidate picker). `grounding.py` verifies every LLM-quoted evidence span against the paper markdown. `chunking.py` splits oversized papers on H2 boundaries and folds per-chunk verdicts. `constants.py` holds every threshold. `cli.py` is the batch loop (`whisker-tapetum-llm`) with a progress bar and a retry-noise filter. `models.py` is the pydantic output schema (`Adjudication`, `AxisFinding`, `EvidenceSpan`, `TapetumResult`). `tapetum_llm.md` is the authority doc (services, cascade steps, full system prompt).

The lane is **advisory only**: it never gates, never overwrites the whisker verdict, and always exits 0 (`cli.py:37`, `cli.py:11-14`).

## Size (LOC, authoritative via file line count)

| Module | LOC |
|---|---|
| `pipeline/model_backends.py` | 768 |
| `pipeline/services.py` | 526 |
| `pipeline/prompt.py` | 519 |
| `pipeline/runner.py` | 415 |
| `pipeline/agents.py` | 172 |
| `pipeline/tasks.py` | ~124 |
| `pipeline/tools.py` | 104 |
| `whisker/tapetum_llm/adjudicate.py` | 441 |
| `whisker/tapetum_llm/cli.py` | 355 |
| `whisker/tapetum_llm/chunking.py` | 244 |
| `whisker/tapetum_llm/tapetum_llm.md` | 162 |
| `whisker/tapetum_llm/models.py` | 124 |
| `whisker/tapetum_llm/inspect_report.py` | 119 |
| `whisker/tapetum_llm/constants.py` | 70 |
| `whisker/tapetum_llm/grounding.py` | 56 |

**Tests (reproduced this run, `def test_` count via grep):** pipeline = 177 test functions across 15 files (`packages/pipeline/tests/test_*.py`); whisker = 325 test functions across 20 files (`packages/whisker/tests/test_*.py`), of which `test_tapetum_llm.py` = 75 and `test_tapetum_llm_eval.py` = 1. Task-reported pytest pass counts (parametrization expands the function count; NOT re-run this session): pipeline 187 passed, whisker 670 passed.

## Runtime facts (batch-run evidence, reproduced read-only)

- **200 papers attempted, 197 advisory sidecars produced.** `data/paperstore/*.debug.tapetum_llm.md` = 200 files (one debug transcript per attempted paper); `data/whisker/*.tapetum.json` = 197 (advisory result sidecars). The 3-file gap is consistent with hard failures that never produced a sidecar. `data/whisker/*.whisker.json` = 381 (the upstream deterministic sidecars).
- **Suggested-verdict distribution over the 197 sidecars: 73 `pass`, 106 `review`, 18 `fail`.** (reproduced by parsing every `*.tapetum.json`.) Review is the plurality outcome (54%).
- **The deep tier NEVER escalated: `escalated=true` in 0 / 197 sidecars.** (reproduced.) deepseek-v4-pro's self-reported confidence never landed inside the ambiguous band `[CONFIDENCE_AMBIGUOUS_LO=0.35, CONFIDENCE_AMBIGUOUS_HI=0.65]` (`constants.py:22-23`, gate at `adjudicate.py:206-208`), so the "two-tier cascade" ran single-tier in production. Compounding: `fast` and `deep` both resolve to the same service `alliance-pod` (`tapetum_llm.md:17-19`), so an escalation would only buy a second pass on the *same* model, not a larger one.
- **9 / 197 sidecars dropped at least one ungrounded evidence span** (`ungrounded_dropped > 0`; reproduced). Grounding is active, not vestigial.
- **The deepseek-v4-pro token-injection artifact is real and captured.** `Select-String` over `data/paperstore/*.debug.tapetum_llm.md` matches `"confidence": <non-digit>0.98`, `"confidence": <non-digit>0.95`, and bare `"confidence": <non-digit>` (stray CJK token glued to the number, rendered as replacement chars in the transcript). This is exactly the artifact `_RAW_JSON_MAX_ATTEMPTS = 3` absorbs (`model_backends.py:76-85`).
- **Failure mode (task-supplied, corroborated by the 3-sidecar gap):** the 200-paper run finished with 9 hard failures, all `"Raw JSON completion failed after 2 attempt(s)"` (the old budget of 2; raised to 3 at `model_backends.py:76`). Throughput ~25-40 s/paper, ~1.5-2 h for 200 papers, strictly serial (`cli.py:277-317`, one `await adjudicate_paper` per iteration).

## Comparison anchors (OUR invariants that constrain any redesign)

The self-target's redesign space is bounded by these governing-doc invariants. A persona proposing "harden / redesign" must show the proposal survives every one it touches.

- **D1** - every LLM call goes through `run_agent`/`run_task`; never construct `pydantic_ai.Agent` or call `chat.completions.create` directly (`CLAUDE.md:80`). NOTE the tension: `VllmThinkingBackend` *does* call `client.chat.completions.create` (`model_backends.py:318`, `:341`) - this is sanctioned because it is *inside* a backend, below the `run_agent` boundary, but any redesign must keep new call sites behind the backend.
- **D4** - never `parallel_tool_calls=True` (`CLAUDE.md:83`; enforced at `model_backends.py:462`, `:554`, `:648`, `:727`).
- **D5** - never override `temperature`/`seed` per call (`CLAUDE.md:84`; pins baked at `model_backends.py:321-323`).
- **D6** - every step declares `output_type=<PydanticModel>`; no free-text->regex (`CLAUDE.md:85`; `Adjudication` at `models.py:72-86`).
- **D7** - sort unordered collections before they feed a prompt (`CLAUDE.md:86`).
- **D9/D10** - `UsageLimits` passed to `run(...)` not `Agent(...)`; pair `output_type` with a finite retry budget (`CLAUDE.md:88-...`; `model_backends.py:480`).
- **D11 (the load-bearing one for concurrency)** - "`dissect` runs with at most one in-flight LLM request at a time. The framework defaults to serial via `_parallel_semaphore` and `_task_semaphore` at `asyncio.Semaphore(1)`. New packages that opt into concurrent execution must do so through a per-package mechanism that leaves dissect on the serial path." (`CLAUDE.md:88`). Reinforced in `MODELS.md:55-65` (concurrency pins) and `packages/pipeline/src/pipeline/CLAUDE.md` D3. So tapetum MAY add bounded concurrency, but only via a per-package/per-context mechanism, never by flipping a global semaphore.
- **Fidelity: fail-not-partial** (`CLAUDE.md`, "Fidelity" section) - a partial read must never become a clean pass (implemented at `adjudicate.py:245-246`, `chunking.py` partial flag).
- **Model sovereignty** (`CLAUDE.md`, "Model sovereignty") - every pipeline must work on `vllm_thinking` backends, not just Anthropic; schema compliance is solved by retries + prompt engineering, not by retreating to a cloud API. This directly constrains RQ2 (guided decoding is a vLLM feature, so it is *compatible* with sovereignty, but any move must keep the self-hosted path first-class).
- **MODELS.md workaround inventory** (`MODELS.md:113-125`) - the deepseek-v4-pro token-injection row (`MODELS.md:121`) names the retire-when: "vLLM guided decoding (`guided_json`) adopted for this backend, or deepseek-v4-pro sampling fix upstream." The schema-in-prompt + raw-JSON-retry rows (`MODELS.md:119-120`) retire when the vLLM unified parser or pydantic-ai VLLMProvider lands.
- **MODELS.md schema-field-count finding** (`MODELS.md:36-53`) - >= 5 fields stabilizes constrained decoding; `Adjudication` carries 7 fields (`models.py:80-86`), satisfying the floor (`models.py:13-16` documents the intent).

## Decision questions (baked in; answer with baseline evidence)

**RQ1 - Can tapetum adopt bounded `--concurrency N` without violating determinism, and where does it hook in?**
Baseline evidence: the batch loop is a plain serial `for pid in pids` (`cli.py:277-317`). The framework already ships an *ordered, bounded* concurrency primitive: `StepContext.gather_concurrent(coros, concurrency, label)` uses `asyncio.Semaphore(concurrency)` and re-sorts results by index so output order is deterministic regardless of completion order (`runner.py:133-162`). D11 (`CLAUDE.md:88`) permits a per-package mechanism that leaves dissect serial. **The clean hook is the CLI batch loop (paper-level fan-out in `cli.py`), NOT `run_agent`/the semaphores** - papers are independent, each `adjudicate_paper` is internally serial, and dissect never touches this path. Raising `_parallel_semaphore`/`_task_semaphore` (`MODELS.md:59-60`) is the forbidden path (global flip). Open sub-question for the Concurrency-Architect: does per-paper concurrency create cross-request batch interference on the shared `alliance-pod` vLLM server that perturbs deepseek confidence (MoE routing caveat, `MODELS.md:69`)?

**RQ2 - Is the 3-attempt raw-JSON retry loop the right mitigation, or should we adopt vLLM guided decoding (`guided_json` / `response_format=json_schema`)?**
Baseline evidence: the artifact is confirmed in transcripts (see Runtime facts); the loop self-corrects it (`model_backends.py:76-85`, retry logic `:382-421`) and splits truncation (grow `max_tokens`, `:388-404`) from malformation (feedback nudge, `:405-417`). Guided decoding is named as the retire-when for both the token-injection row and the schema-in-prompt row (`MODELS.md:119-121`). Cost to weigh: guided decoding's grammar mask can interact badly with `<think>` blocks (the backend strips `<think>...</think>` at `_strip_think_block`, `model_backends.py:104-112`) - if the grammar activates during reasoning it corrupts thinking; this is the exact hazard the schema-in-prompt approach sidesteps. Model-sovereignty (`CLAUDE.md`) is *satisfied* by guided decoding (it is a vLLM/self-hosted feature), so the tradeoff is thinking-compatibility and determinism, not sovereignty. Web questions 1, 2, 4 feed this.

**RQ3 - Is evidence grounding robust?**
Baseline evidence: `ground_spans` (`grounding.py:24-56`) grounds a span if its `normalized_text` quote is a substring of the normalized markdown, OR `rapidfuzz.partial_ratio >= EVIDENCE_FUZZY_FLOOR = 0.90` (`constants.py:50`). Empty normalized quotes are dropped (`grounding.py:45-47`). Ungrounded non-pass verdicts demote to review (`adjudicate.py:237-238`); 9/197 papers exercised a drop (reproduced). Open sub-questions for the Grounding-Robustness-Auditor and False-Positive/Negative hunters: `partial_ratio` at 0.90 on a *whole-document* haystack - can a short generic quote (e.g. `"the following"`) fuzzy-match anywhere and ground a fabricated span (false-pass)? Does `normalized_text` (whisker's OmniDocBench normalizer, folds LaTeX/strips to alnum+CJK) erase the very characters (`^`, `_`, `|`, brackets) whose corruption the math/tables/stable_names axes exist to catch, so a real defect grounds anyway (false-negative)?

**RQ4 - Hidden determinism defects?**
Baseline evidence + a surprise found this run: **per-step `**max-output:**` and `**thinking-budget:**` declared in the authority doc are parsed but never applied.** `tapetum_llm.md` declares Triage `max-output 2048 / thinking-budget 1024` (`tapetum_llm.md:118-119`) and Adjudicate `max-output 4096 / thinking-budget 4096` (`tapetum_llm.md:137-139`); `StepPrompt` parses them into `max_output_tokens` / `thinking_budget` (`prompt.py:108-115`, `:389-390`); `AgentBackend.run` accepts per-call overrides and its docstring says "Per-step overrides come from `StepMeta.max_output_tokens` via the runner" (`agents.py:117-133`); **but `run_agent` never forwards them** - it calls `agent.run(system, user_msg, output_type, tools=..., label=..., debug_log=..., request_limit=...)` with no `max_tokens`/`thinking_budget` (`runner.py:266-272`). So every tapetum call runs at the construction-time `max_tokens=4096` (`adjudicate.py:391`) with `thinking_budget=None` (thinking effectively off). This is a documented-contract-vs-behavior gap for API-Contract-Design / Documentation-Claims / Determinism to verify and rank. Other RQ4 seeds: `dict` iteration into prompts, `select_candidates` returns sorted (`adjudicate.py:94`, good), `to_dict` sorts spans (`models.py:116-119`, good), aggregation sorts axes (`chunking.py:184`, good).

---

## Persona roster (22 total)

Generic core (01-17) + ad-hoc LLM-adjudication personas (18-22). Format: NN | name | mandate | failure class it hunts.

| NN | Name | Mandate | Failure class |
|---|---|---|---|
| 01 | Security-Reviewer | injection, unsafe deserialization, secret handling, trust boundaries | exploitable input path reaching a dangerous sink (esp. `json.loads` on model output `model_backends.py:374`, `.env` key handling `cli.py:346-348`) |
| 02 | License-Compliance | dep licenses, copied-code provenance, BSL-1.0 header hygiene | a dependency license (rapidfuzz, openai, pydantic-ai, apted) that forbids our adoption/redistribution |
| 03 | Determinism-Auditor | run-to-run variance, ordering, seeds, unordered iteration | a source of non-reproducible verdicts across identical runs |
| 04 | API-Contract-Design | public surface, return shapes, docstring-vs-behavior | a contract the docs promise the code breaks (RQ4 max-output/thinking-budget) |
| 05 | Maintainability-Complexity | coupling, dead code, god-modules, duplication | structure that will rot (e.g. dead tier2 path, escalated=0) |
| 06 | Performance-Scalability | hot paths, I/O in loops, O(n^2), wall-clock | a cost that explodes with batch size (1.5-2 h / 200 papers, serial) |
| 07 | Test-Suite-Auditor | coverage gaps, vacuous asserts, missing edge cases | a test that passes while behavior is wrong (esp. no test caught max-output/thinking-budget non-wiring) |
| 08 | Documentation-Claims | authority-doc / CLAUDE.md / docstring vs implementation | a documented claim the code contradicts (per-step budgets, "two-tier cascade") |
| 09 | Error-Handling-Robustness | swallowed exceptions, partial failure, resource leaks | a failure that corrupts or hides data loss (broad `except Exception` `cli.py:304`, 3-sidecar gap) |
| 10 | Adversary-Evasion | make the fidelity check pass while output is bad | a false-pass exploit via crafted markdown or forged guard delimiters |
| 11 | False-Positive-Hunter | over-strict gates, noise | a faithful conversion the lane wrongly flags review/fail (106/197 review rate) |
| 12 | False-Negative-Hunter | blind spots | a corrupted conversion the lane wrongly passes (73/197 pass) |
| 13 | Dependency-Supply-Chain | transitive deps, pinning, abandoned packages | a fragile/risky dependency (pydantic-ai version churn, vLLM/openai coupling) |
| 14 | Portability-Platform | OS/path/encoding assumptions | code that breaks off Windows/the author's machine (path building, CRLF, unicode) |
| 15 | Downstream-Consumer | integrator experience of the framework | a sharp edge that traps a new pipeline author (silent per-step-budget drop) |
| 16 | Product-Decision-Skeptic | does the advisory lane solve the stated blind-spot problem | a mismatch between "second opinion on fidelity" claim and delivered value |
| 17 | Steelman | strongest honest case FOR the stack; keep the verdict fair | over-harsh consensus that misses real strengths (grounding, guard, fail-not-partial) |
| 18 | Concurrency-Architect | where/how bounded `--concurrency N` hooks in without breaking D11 | a concurrency design that flips a global semaphore or perturbs shared-pod determinism (RQ1) |
| 19 | Schema-Compliance-Auditor | schema-in-prompt vs vLLM guided decoding, thinking-block compatibility | a structured-output strategy that corrupts `<think>` output or breaks on smaller models (RQ2) |
| 20 | Retry-Policy-Analyst | the 3-attempt loop, truncation-vs-malformation split, feedback nudge | a retry policy that masks a systematic failure or loops unboundedly (RQ2) |
| 21 | Cascade-Calibration-Statistician | the ambiguous band, confidence floor, escalated=0, verdict distribution | mis-calibrated thresholds that make the cascade single-tier or over-review (RQ4-adjacent) |
| 22 | Grounding-Robustness-Auditor | fuzzy floor 0.90, whitespace/LaTeX normalization, drop-vs-demote | grounding that accepts a fabricated quote or rejects a genuine one (RQ3) |

## Web questions (code cannot answer; {question, search_query})

1. **{question:** Are vLLM guided decoding (`guided_json`) / structured outputs compatible with thinking/reasoning models that emit `<think>` blocks, and does the grammar mask corrupt the reasoning segment? **search_query:** `vLLM guided_json structured output reasoning models think blocks compatibility 2026`}
2. **{question:** Is the DeepSeek (V3/R1/V4-class) artifact of injecting stray CJK/garbage tokens into otherwise-valid JSON a reported, reproducible issue, and what mitigations do others use? **search_query:** `DeepSeek model random CJK tokens injected into JSON output invalid decoding issue`}
3. **{question:** What is the canonical asyncio pattern for bounded-concurrency that preserves input order for a deterministic batch of LLM calls? **search_query:** `asyncio bounded concurrency semaphore preserve order gather batch LLM requests deterministic`}
4. **{question:** Does vLLM's OpenAI-compatible server support `response_format={"type":"json_schema"}`, and how does it interact with `temperature=0` / seed determinism? **search_query:** `vLLM OpenAI compatible server response_format json_schema support determinism 2026`}
5. **{question:** What are the known failure modes of retry-with-error-feedback loops for LLM structured output (context bloat, error misattribution, non-convergence)? **search_query:** `LLM retry with error feedback structured output failure modes context bloat convergence`}

---

## Required persona report template (every persona writes this shape, verbatim)

```
# NN - <Persona name>

**Verdict:** usable | usable-with-conditions | garbage   (+ 1 sentence why)
**Confidence:** high | medium | low

## Findings
- [CRITICAL|HIGH|MED|LOW] <claim>. Evidence: <file:line OR runtime number from 00>.
  Impact: <why it makes the target more/less trustworthy or adoptable>.
  (repeat; 3-8 findings, ranked)

## False-pass hypothesis
<one concrete case the target/our-equivalent would wrongly accept, or "none found">

## False-fail hypothesis
<one concrete case it would wrongly reject, or "none found">

## What would change my mind
<the single piece of evidence that would flip my verdict>
```
