# Opus Meta-Review C - Engineering Quality (llm-stack)

Scope: maintainability, coupling (tapetum_llm <-> pipeline), dead code, test-suite
quality, error handling, dependency hygiene, portability. Personas re-verified:
02, 04, 05, 07, 08, 09, 13, 14, 15. Every anchor below was reopened at HEAD.

**Freshness correction applied.** The raw-JSON retry budget was reverted after the
baseline: current code is `max_attempts = min(2, request_limit)`
(`model_backends.py:300`). There is no `_RAW_JSON_MAX_ATTEMPTS = 3` constant, the
final error message emits `"... after 2 attempt(s)"` (`model_backends.py:407-410`),
and `test_double_corruption_recovers_on_third_attempt` no longer exists
(`test_truncation_retry.py` ends at line 141 with four tests, all 2-attempt). Every
persona claim keyed to a 3-attempt budget was re-checked and is handled below.

---

## Verified claims (persona-file: claim -> CONFIRMED, evidence)

**The load-bearing engineering defect (confirmed independently by 5 personas):**

- **[04/05/07/08/15] Per-step `max-output`/`thinking-budget` are parsed but `run_agent`
  never forwards them -> CONFIRMED.** `run_agent` calls `agent.run(system, user_msg,
  output_type, tools=..., label=..., debug_log=..., request_limit=...)` with no
  `max_tokens`/`thinking_budget` (`runner.py:266-272`). The fields parse into the
  dataclass (`prompt.py:389-390`, `StepPrompt.max_output_tokens`/`thinking_budget` at
  `prompt.py:108-115`). `AgentBackend.run` accepts both overrides and resolves `None`
  to construction defaults (`agents.py:117-118`, `:149-150`). tapetum builds every
  agent at flat `max_tokens=4096` (`adjudicate.py:391`) and passes no `thinking_budget`,
  so the vLLM thinking branch is never taken (`extra` stays empty when
  `thinking_budget is None`, `model_backends.py:294-298`): thinking is off and triage
  runs at 4096, not the doc's 2048/1024. CONFIRMED live and unchanged by the revert.

- **[04/08] `agents.py` docstring is an active false claim -> CONFIRMED.** The
  docstring states "Per-step overrides come from `StepMeta.max_output_tokens` via the
  runner" (`agents.py:127-128`, `:132-133`); `run_agent` reads neither
  `spec.step.max_output_tokens` nor `spec.step.thinking_budget` (`runner.py:266-272`).

- **[07] No test guards budget forwarding -> CONFIRMED.** `test_runner.py` contains
  zero references to `max_output_tokens`, `thinking_budget`, `run_agent`, or
  `agent.run` (grep: no matches). `test_tapetum_llm.py:256-257` sets
  `mock_spec.step.max_output_tokens = 2048` / `thinking_budget = 1024` on a mock but
  never asserts them at the `run_agent`/`agent.run` boundary. The regression is
  unguarded in both directions.

**Maintainability / coupling / dead code (05):**

- **[05] Two-tier cascade is dead in production -> CONFIRMED (code) + baseline
  runtime.** Escalation gate `confidence < CONFIDENCE_AMBIGUOUS_LO or > _HI`
  (`adjudicate.py:206-208`); step `"2. Adjudicate"` exists (`adjudicate.py:284`) but
  `fast`/`deep`/`default` all bind to `alliance-pod` (`tapetum_llm.md:17-19`), so even
  a fired escalation is a second pass on the same model. `escalated=true` in 0/197
  sidecars is a baseline runtime fact I did not re-run but the code fully supports it.

- **[05] `model_backends.py` carries four copy-paste `Agent.run` bodies; Anthropic has
  drifted -> CONFIRMED.** `VllmThinkingBackend._run_with_tools` (`:447-479`),
  `Llama3Backend.run` (`:514-572`), `Qwen3Backend.run` (`:606-667`),
  `AnthropicBackend.run` (`:696-745`) each repeat: lazy pydantic-ai imports,
  `ModelSettings(temperature=0.0, parallel_tool_calls=False, ...)`, `Agent(retries=3)`,
  the tool-registration loop, `UsageLimits(request_limit=...)`, and the
  `UsageLimitExceeded`/`add_note` handler. Anthropic's `ModelSettings` omits `top_p`
  and `seed` (`:714-718`) that Llama3 sets (`:541-542`); only Qwen3 adds `extra_body`
  (`:631`, `:639`). The drift the persona predicted is present. (Line numbers sit ~11
  above the baseline's because the retry revert removed lines; the structure is
  unchanged.)

- **[05] `_PipelineState._result` is a dynamic-attribute hack -> CONFIRMED.**
  `state._result = result  # type: ignore[attr-defined]` (`adjudicate.py:272`), read
  back via `getattr(state, "_result", None)` (`adjudicate.py:427`); the dataclass
  declares `tier1/tier2/chunked/partial` but not `_result` (`adjudicate.py:136-149`).

- **[05] Cross-module private coupling `cli.py` -> `whisker.__main__._render_progress`
  -> CONFIRMED.** `from whisker.__main__ import _render_progress` (`cli.py:30`), used
  at `cli.py:263`, `:267`. `_BATCH_QUIET_LOGGERS` hard-codes pipeline logger names
  `"pipeline.runner"`, `"pipeline.services"`, `"httpx"`, `"openai"` (`cli.py:43-48`)
  and mutates their levels at runtime (`cli.py:252-253`): a rename in pipeline
  silently restores per-paper log spam with no compile-time signal.

- **[05 LOW] Chunked oversized papers permanently skip tier2 -> CONFIRMED.**
  `if state.chunked: return` with the "later upgrade" comment (`adjudicate.py:200-204`).

**Error handling (09):**

- **[09] Rerun failure leaves a stale `*.tapetum.json` -> CONFIRMED.** The batch
  worker's `except Exception` increments `counts["error"]`, logs one line, and writes
  nothing (`cli.py:304-315`); `_persist_result` runs only on the success path
  (`cli.py:289`). No delete/tombstone/error-sidecar exists. A prior `pass` sidecar
  survives a failed rerun. (The failure string is now "... after 2 attempt(s)", not 3;
  the finding is unaffected.)

- **[09] Hard failures produce no structured sidecar -> CONFIRMED (code).** Only an
  ERROR log line on the exception path (`cli.py:304-311`); the 200-debug vs 197-sidecar
  gap is the baseline runtime corroboration.

- **[09] `TapetumResult.to_dict` omits `partial`/`chunked` -> CONFIRMED.**
  `to_dict` emits pid, verdicts, confidence, models, axes, evidence, dropped, concern,
  reasoning, `advisory:true` and nothing else (`models.py:106-124`); a consumer cannot
  tell a partial-read review from a full-document one.

- **[09] Partial demotion is pass-only -> CONFIRMED.** `if state.partial and
  suggested_verdict == VERDICT_PASS` (`adjudicate.py:245-246`); a `fail`/`review` from
  an incomplete read stands unflagged.

- **[09 MED] `_result is None` fallback returns a normal-looking review -> CONFIRMED.**
  `suggested_verdict=VERDICT_REVIEW, confidence=0.0, primary_concern="pipeline did not
  produce a result"` (`adjudicate.py:428-439`), with no error/failed field to
  distinguish an aborted run from a content-driven review.

- **[09 MED] Inconsistent corrupt-sidecar handling -> CONFIRMED.**
  `_collect_sidecar_dicts` swallows `json.JSONDecodeError`/`OSError` and `continue`s
  with no log (`cli.py:182-186`); `_custom_select` reads the same artifact with bare
  `json.loads(...)` that raises and fails the paper (`adjudicate.py:164-165`).

- **[09 MED] Exit code is always 0 despite errors -> CONFIRMED.** `_EXIT_OK = 0`
  (`cli.py:37`), `sys.exit(_EXIT_OK)` unconditionally (`cli.py:351`).

**Test-suite quality (07):**

- **[07] Malformation-nudge feedback is vacuously asserted -> CONFIRMED.** The code
  appends the corrective turn with `Error: {exc}` (`model_backends.py:398-405`);
  `test_malformation_nudges_and_holds_budget` only asserts `"valid JSON" in
  ...messages[-1]["content"]` (`test_truncation_retry.py:103-119`), never that the
  error detail is forwarded. Dropping `Error: {exc}` would stay green.

- **[07 MED] Confident-pass-with-all-evidence-ungrounded is unguarded -> CONFIRMED
  (code).** The demotion guard fires only for non-pass verdicts (`adjudicate.py:237-238`);
  a `pass` with every span dropped keeps `pass`. This is the same false-pass channel
  RQ3 names.

**API contract / downstream (04/15):**

- **[04 MED] Docstrings reference a phantom `StepMeta`; the public type is
  `StepPrompt` -> CONFIRMED.** The dataclass is `StepPrompt` (`prompt.py:73`); the
  public re-export is `StepPrompt` (`__init__.py:43`, `:156`). `StepMeta` appears only
  in `agents.py:128`/`:133` docstrings and `pipeline/CLAUDE.md:12`/`:34` (a re-export
  list that is itself wrong). No `StepMeta` symbol exists.

- **[04/15] Authority-doc control planes parsed but not consumed by `dispatch`
  -> CONFIRMED.** `dispatch` honors only `hooks.custom`, `hooks.parallel`, `hooks.guard`
  (`runner.py:355-384`); `execution`/`condition`/`concurrency` parse into `StepPrompt`
  (`prompt.py:384`, `:386`, `:392`) with no runtime consumer. tapetum hardcodes
  `default_concurrency=1` (`adjudicate.py:409`) rather than reading `prompt.config`.

- **[04] `dispatch` parallel branch runs the fan-out serially -> CONFIRMED.** Plain
  `for msg in user_msgs: await run_agent(...)` (`runner.py:369-373`); the docstring
  admits "sequentially" (`runner.py:299`). `gather_concurrent` exists
  (`runner.py:133-162`) but is unused by `dispatch`.

- **[15] D11's `_parallel_semaphore` is a dead doc reference -> CONFIRMED.** grep finds
  `_parallel_semaphore` only in `CLAUDE.md:88`, `pipeline/CLAUDE.md:89`, `MODELS.md:59`
  and never in `runner.py`; the only real semaphore is `_task_semaphore`
  (`tasks.py:38`). `default_concurrency` on `StepContext` (`runner.py:106`) is never
  set by the framework.

- **[15 LOW] Malformed numeric metadata bypasses `PromptFileError` -> CONFIRMED.**
  `_opt_int` uses bare `int(raw)` (`prompt.py:371-372`); `**max-output:** not-a-number`
  raises `ValueError`, not the promised structural error.

**Dependency hygiene (13) and license (02):**

- **[13/02] `pydantic-ai` and `openai` are declared with no version floor
  -> CONFIRMED.** `whisker/pyproject.toml:28` bare `"pydantic-ai"`;
  `pipeline/pyproject.toml:10-11` bare `"openai"` and `"pydantic-ai-slim"`;
  `sentence-transformers`/`httpx`/`trafilatura` also bare (`pipeline/pyproject.toml:9-13`).
  `rapidfuzz>=3.14.5,<4` (`whisker/pyproject.toml:17`) is the positive counterexample.

- **[02 MED] No consolidated third-party NOTICE despite Apache-2.0 deps and verbatim
  OmniDocBench ports -> CONFIRMED.** Glob for `NOTICE*`/`THIRD_PARTY_NOTICES*` across
  the workspace returns zero files. `grounding.py:19` imports `normalized_text` from
  `whisker.metrics` (the OmniDocBench normalizer per `whisker/CLAUDE.md`). BSL-1.0
  headers are present on every LLM-stack module I opened (pipeline + tapetum_llm).

**Portability (14):**

- **[14] `SERVICES.toml` discovery is `Path.cwd()`-only -> CONFIRMED.**
  `_find_services_toml` walks `[here, *here.parents]` from `Path.cwd()`
  (`services.py:87-94`); `load_services()` calls it when `path` is omitted
  (`services.py:127-128`); tapetum calls `load_services()` with no path
  (`adjudicate.py:379`). A cwd outside the checkout raises `FileNotFoundError`
  (`services.py:129-133`).

- **[14] `.env` hydration is cwd-coupled -> CONFIRMED.**
  `load_dotenv(find_dotenv(usecwd=True))` (`cli.py:348`) searches upward from cwd only.

- **[14] tapetum `WG21_DATA_DIR` resolution skips the `.strip()` paperstore enforces
  -> CONFIRMED.** `os.environ.get("WG21_DATA_DIR", "")` with no strip (`cli.py:158`); a
  trailing newline/space opens a non-existent dir.

---

## Downgraded/dropped claims

- **[07 HIGH] "`request_limit` cap untested against the double-corruption scenario"
  / "`test_double_corruption_recovers_on_third_attempt` proves three attempts recover"
  -> DROPPED.** Evidence does not reproduce at HEAD. Current budget is
  `max_attempts = min(2, request_limit)` (`model_backends.py:300`); there is no
  `_RAW_JSON_MAX_ATTEMPTS` and no `model_backends.py:311`. `test_truncation_retry.py`
  has four tests and ends at line 141; the named third-attempt test is gone. A "recover
  on the third attempt" scenario is impossible with a 2-attempt budget, so the finding
  as written is moot. (A weaker, still-valid residue: `test_truncation_retry.py` never
  varies `request_limit`, but the double-corruption framing no longer applies.)

- **[07/20] "three malformation attempts recover" -> DROPPED** for the same reason
  (2-attempt budget; `test_persistent_truncation_raises` confirms failure after
  exactly two, `test_truncation_retry.py:132-140`).

- **[09 LOW / 13 MED] "Raw JSON completion failed after 3 attempt(s)" /
  "3-attempt budget at `model_backends.py:76-85`" -> DOWNGRADED (stale detail, finding
  survives).** The message now reads "... after 2 attempt(s)" (`model_backends.py:408`),
  and `:76-85` is now the `_RETRY_MAX_TOKENS_GROWTH` docstring, not a budget constant.
  The findings these anchors support (09's stale-sidecar CRITICAL; 13's unpinned-dep
  HIGH) rest on other, still-valid evidence and remain CONFIRMED.

- **[02] Exact SPDX identifiers (rapidfuzz MIT, openai/trafilatura Apache-2.0,
  pydantic-ai/httpx/python-dotenv MIT/BSD) and the "17 pipeline + 8 tapetum files all
  BSL" count -> NOT INDEPENDENTLY REPRODUCED.** I confirmed the manifest declarations
  and BSL headers on every file I opened, but did not re-derive runtime license
  metadata or re-count every module, so I hold these at the persona's stated confidence
  rather than upgrading them.

- **[14] "the main `paperflow` CLI never loads dotenv" -> PARTIALLY VERIFIED.** The
  tapetum-side `load_dotenv` at `cli.py:348` is confirmed; I did not grep `packages/cli/`
  to confirm the negative, so that half is unverified. Does not change the portability
  conclusion.

---

## Net assessment (3-6 sentences)

The engineering-quality persona reports are unusually accurate: the dominant finding,
that the runner silently drops authority-doc `max-output`/`thinking-budget` and that no
test guards the wiring, is fully confirmed at HEAD across five independent personas and
is the single highest-leverage defect in the stack (docstring-vs-behavior contract
break, thinking-off in production, unguarded regression). The maintainability critique
holds: a dead two-tier cascade, four copy-paste backend bodies with visible Anthropic
sampling drift, a `type: ignore` result-passing hack, and hard cross-package coupling
(`whisker.__main__._render_progress`, pipeline logger names) are all real. Error
handling has a genuine data-integrity hole: a failed rerun leaves a stale `pass`
sidecar with no tombstone and always exits 0, and `to_dict` hides the `partial` flag
from consumers. The one place the reports have gone stale is the retry budget: it was
reverted from 3 back to `min(2, request_limit)`, which drops persona 07's
"double-corruption / third-attempt" test claim entirely and turns several "3 attempt(s)"
anchors into 2, though the findings those anchors merely decorated survive on other
evidence. Net: the stack is usable-with-conditions, and the conditions the personas name
(wire the step budgets + add a forwarding test, split `fast`/`deep` or rewrite the
cascade doc, tombstone failed reruns, pin the LLM SDKs) are the correct engineering
punch-list.
