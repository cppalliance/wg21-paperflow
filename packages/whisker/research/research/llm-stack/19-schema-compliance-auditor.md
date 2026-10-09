# 19 - Schema-Compliance-Auditor

**Verdict:** usable-with-conditions — schema-in-prompt + the 3-attempt raw-JSON loop is the correct default today; pod upgrade (#42287) is the cheapest first lever, and `response_format=json_schema` is adoptable only after the alliance-pod runs vLLM ≥ 0.20.1 with `--reasoning-parser deepseek_v4` and the #41199 routing fix, with the retry loop kept as fallback.
**Confidence:** medium

## Findings

- [HIGH] The batch CJK-in-JSON artifact is a vLLM MLA-decode precision bug, not merely greedy sampling variance: issue #41985 attributes ~50–75% injection at temperature=1.0 to FP8 MLA attention in vLLM's custom decode path; our pod already pins `temperature=0.0` (`model_backends.py:321-323`) yet 9/200 papers still hit double corruption absorbed by `_RAW_JSON_MAX_ATTEMPTS = 3` (`00-baseline.md:48`, `model_backends.py:76-85`, `MODELS.md:121`). Merged fix #42287 eliminates bad tokens at the decode layer (`05-web.md:30-32`, https://github.com/vllm-project/vllm/issues/41985). Impact: upgrading the pod is cheaper and lower-risk than rewriting the backend first; it directly retires the primary retire-when row in `MODELS.md:121` without touching pipeline code.

- [HIGH] vLLM V1 defers grammar masking until reasoning ends when `--reasoning-parser` is set: PR #16577 (landed v0.9.0+) makes xgrammar skip the `<think>` segment and apply JSON schema only to the post-reasoning `content` stream (`05-web.md:16-18`, https://github.com/vllm-project/vllm/pull/16577). Our backend sidesteps the pre-0.9 hazard by schema-in-prompt and client-side `_strip_think_block` (`model_backends.py:104-112`, `296-297`, `363`). Impact: adopting server-side `response_format` is thinking-safe on modern vLLM, but only when the server actually runs V1 + reasoning parser; the client-side strip path must remain until every pod is verified.

- [HIGH] DeepSeek-V4-Pro + thinking + structured output misroutes JSON without #41199: issue #41132 reproduces valid JSON in `reasoning` with `content=None` under `--reasoning-parser deepseek_v4` and `enable_thinking: True`; fix merged in PR #41199, milestone **v0.20.1** (https://github.com/vllm-project/vllm/pull/41199). Our non-tool path parses JSON from stripped `content` only (`model_backends.py:363-374`); server-side misrouting would empty `content` and burn retries. Impact: `response_format=json_schema` is blocked on alliance-pod until vLLM ≥ 0.20.1 with #41199; smoke-test before flipping the backend.

- [MED] `response_format={"type":"json_schema",...}` is the supported OpenAI wire contract; `guided_json` is deprecated since v0.12.0 (`05-web.md:74-76`, https://docs.vllm.ai/en/stable/features/structured_outputs/). `VllmThinkingBackend` never sends `response_format` today — it appends `_schema_instruction` to the system prompt and relies on `_extract_json` + `json.loads` (`model_backends.py:136-143`, `296-297`, `318-327`). Impact: adoption is a localized backend change (add `response_format` kwarg, drop schema block when active), not a framework rewrite.

- [MED] The 3-attempt retry loop cannot be fully retired even after guided decoding: it splits truncation (`finish_reason == "length"` → grow `max_tokens`, `model_backends.py:388-404`) from malformation (error-feedback nudge, `405-417`), and vLLM silently falls back to unconstrained generation on invalid/incomplete JSON schema (`05-web.md:92`). Measured 9 hard failures at the old 2-attempt budget (`00-baseline.md:49`). Impact: keep `_RAW_JSON_MAX_ATTEMPTS` as defense-in-depth; guided decoding reduces malformation retries, it does not eliminate them.

- [MED] DeepSeek-V4 thinking activation uses `enable_thinking` in `chat_template_kwargs`, but our backend sends `thinking_token_budget` or `enable_thinking: False` (`model_backends.py:305-309`); vLLM docs require `enable_thinking: true` for V4 to emit thinking tokens at all (`05-web.md:14`). #41199 forwards `reasoning_parser_kwargs` from the same kwargs into the structured-output gate. Impact: any guided-decoding rollout must align client kwargs with server parser semantics before enabling thinking on the structured path.

- [LOW] `Adjudication` carries 7 pydantic fields, above the ≥5-field constrained-decoding stability floor measured on Qwen3 (`MODELS.md:36-53`, `00-baseline.md:65`, `models.py:80-86`). Impact: if alliance-pod adopts `response_format=json_schema`, the schema width is already adequate; no dummy-field hack needed (unlike `Qwen3Backend`'s `unused1`/`unused2`, `model_backends.py:595-598`).

- [LOW] Smaller / mixed-family pods still need schema-in-prompt fallback: Qwen3 constrained decoding can activate too early after `` (#39677, `model_backends.py:595-598`); R1-class pods need `--reasoning-parser deepseek_r1` not `deepseek_v4` (`05-web.md:9-10`, `18`). Impact: `response_format` adoption must be per-service capability flag in `SERVICES.toml`, not a global `VllmThinkingBackend` flip.

## False-pass hypothesis

Pod upgraded with #42287 only (no `response_format`): a stray token corrupts a non-numeric string field (not the observed `"confidence": 极0.98` pattern) in a way that remains valid JSON and passes pydantic validation on attempt 1, producing a semantically wrong but schema-valid `Adjudication`. Unlikely for numeric `confidence` but possible for free-text `reasoning`/`primary_concern` if corruption is whitespace-only.

## False-fail hypothesis

Adopt `response_format=json_schema` on a pod at v0.20.0 (pre-#41199) with thinking enabled: vLLM emits conformant JSON inside the reasoning segment; `_strip_think_block` moves it to `reasoning`, leaving `content` empty; `_extract_json` raises `MalformedModelOutputError` (`model_backends.py:104-112`, `115-124`); all 3 attempts exhaust with `"Raw JSON completion failed"` (`418-421`).

## What would change my mind

A version probe of alliance-pod confirming vLLM ≥ 0.20.1 containing #42287 and #41199, plus 50 consecutive smoke calls with `response_format=json_schema`, `--reasoning-parser deepseek_v4`, `enable_thinking: true`, and `Adjudication` output validating on attempt 1 with zero CJK artifacts in debug transcripts — would flip the verdict to **usable** and justify making guided decoding the primary path with retry as fallback only.

## Adoption preconditions

Concrete checklist for alliance-pod (`SERVICES.toml:64-74`, `backend = "vllm_thinking"`, `model = "deepseek-v4-pro"`):

### (a) Can we adopt `response_format=json_schema` TODAY?

| Precondition | Required value | Evidence |
|---|---|---|
| vLLM version | **≥ 0.20.1** (contains #41199 DeepSeek-V4 structured-output routing) | https://github.com/vllm-project/vllm/pull/41199 (milestone v0.20.1) |
| Thinking + grammar coexistence | **≥ 0.9.0** V1 engine (PR #16577); practically satisfied if ≥ 0.20.1 | `05-web.md:16-18` |
| Wire API | `response_format={"type":"json_schema","json_schema":{...}}` — not deprecated `guided_json` | `05-web.md:74-76` |
| Server flags | `--reasoning-parser deepseek_v4` (not `deepseek_r1`) | `05-web.md:24-26`, issue #41132 repro |
| Structured-output backend | `--guided-decoding-backend xgrammar` (or `--structured-outputs-config.backend`) | `05-web.md:18`, `74-76` |
| Client thinking kwarg | `extra_body={"chat_template_kwargs": {"enable_thinking": true}}` when thinking is on; must match server parser kwargs forwarded by #41199 | `05-web.md:14`, `model_backends.py:305-309` |
| CJK injection fix | Build containing **#42287** (may require nightly post-0.20.2; confirmed on `vllm-openai:nightly-pr42287`) | `05-web.md:30-32`, https://github.com/vllm-project/vllm/issues/41985 |
| Schema validity | Pydantic `model_json_schema()` must be complete; invalid schema → vLLM silent unconstrained fallback | `05-web.md:92` |
| Backend code change | Add `response_format` to `chat.completions.create`; gate on per-service capability; keep `_strip_think_block` until server returns clean `content` | `model_backends.py:318-327` (no `response_format` today) |

**Answer:** Not until pod version is verified. Minimum stack: **vLLM ≥ 0.20.1 + #42287 + `--reasoning-parser deepseek_v4`**. Then implement opt-in in `VllmThinkingBackend` behind a `SERVICES.toml` flag (e.g. `structured_output = true`).

### (b) Fallback for models/pods without guided decoding

Keep unchanged for any pod missing the preconditions above:

1. **Schema-in-prompt** via `_schema_instruction` (`model_backends.py:136-143`, `296-297`).
2. **Client-side think strip** via `_strip_think_block` (`model_backends.py:104-112`).
3. **Raw JSON extract + 3-attempt retry** with truncation-vs-malformation split (`model_backends.py:76-85`, `311-421`).
4. **BPE cleanup** (`model_backends.py:88-101`).
5. **Per-backend registry** — do not flip `BACKEND_REGISTRY` globally (`model_backends.py:763-768`); Qwen3/R1 pods keep current path until their parser + version matrix is verified (`model_backends.py:595-598`).

Retire-when rows in `MODELS.md:117-121` remain accurate: fallback stays until unified parser OR pydantic-ai VLLMProvider (#3515) OR per-pod guided decoding is proven on production traffic.

### (c) Does #42287 alone make the whole question cheaper?

**Partially yes — upgrade first, guided decoding second.**

| Question | #42287 upgrade alone | + `response_format=json_schema` |
|---|---|---|
| CJK glued to JSON numbers | Fixes root cause at decode (`05-web.md:30-32`) | Adds per-token mask as defense-in-depth (`05-web.md:46-48`) |
| Retry loop | Still needed for truncation + schema fallback | Reduced malformation retries, not eliminated (`model_backends.py:388-417`) |
| Backend code change | **None** | Localized `VllmThinkingBackend` change |
| Thinking compatibility | Unaffected (no grammar change) | Requires #41199 + reasoning parser (`05-web.md:16-26`) |
| Smaller models on other pods | N/A | Still need fallback (#39677) |

**Recommendation sequence:**

1. **Now:** Upgrade alliance-pod to vLLM build with #42287; re-run 200-paper batch; expect hard-failure count to drop without code changes.
2. **After version probe ≥ 0.20.1:** Add opt-in `response_format=json_schema` behind service flag; smoke-test 50 calls with thinking on.
3. **Always:** Retain `_RAW_JSON_MAX_ATTEMPTS = 3` as bounded fallback (`model_backends.py:76-85`, D10 in `CLAUDE.md:88`).

Upgrading the pod is the cheapest win; guided decoding is the structural hardening step once the version matrix is confirmed — not a substitute for the retry loop.
