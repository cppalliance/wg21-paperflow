# 05n - Web: DeepSeek V4 + pydantic/JSON schema / guided-decoding latency

**Verdict:** usable-with-conditions — V4 hosted API gives **JSON syntax**
(`json_object`), not full `json_schema` on final content; latency wins there
are mostly **disable thinking**, Flash vs Pro, and slim prompt examples.
Self-hosted V4-Pro on vLLM (alliance-pod) can add **guided JSON** via
XGrammar/llguidance; that path is near-free only for **small, fixed, reused**
schemas and hurts badly on complex/unique nests, Outlines fallback, or short
outputs where compile/mask fixed cost dominates. Schema-slim tactics below
are community-validated across vLLM / XGrammar / SqueezeBits / production
guides; magnitudes for *our* UnitCheck on V4-Pro remain unmeasured here.

**Confidence:** high on mechanisms and slim checklist; medium on %-of-baseline
for alliance-pod (no local A/B); low on "DeepSeek V4 official guided-JSON
bench" (public docs emphasize `json_object` + client Pydantic, not server
grammar numbers).

**Date:** 2026-07-24. Cross-refs: `research/cold-run-10min/05i-web-guided-decoding-cost.md`,
`research/cold-run-10min/62-schema-slim-web.md`, `00-baseline.md` (single pod).

---

## Findings

- [CRITICAL] **Hosted DeepSeek V4 structured path ≠ server `json_schema`.**
  Official docs: `response_format: {type: json_object}` only (`text` |
  `json_object`). Must put the word `json` + an **example shape** in the
  prompt; set `max_tokens` so JSON is not truncated (`finish_reason=length`);
  empty `content` is a known occasional failure. Strict JSON Schema lives on
  **beta tool calling** (`strict: true`), not final-message content.
  Evidence: https://api-docs.deepseek.com/guides/json_mode/ ,
  https://api-docs.deepseek.com/api/create-chat-completion/ ,
  community guides (deepseekai.guide / chat-deep.ai).
  Impact: for cloud V4, "slim schema" mainly means **smaller example + fewer
  fields the model must emit**, plus client Pydantic validate/retry — not
  XGrammar compile cost. For alliance-pod vLLM, enabling
  `response_format` / guided JSON is a separate A/B on top of today's
  schema-in-prompt `VllmThinkingBackend`.

- [CRITICAL] **V4 thinking default dominates structured-call wall.**
  V4 defaults to thinking (`reasoning_effort` high unless disabled). Guides
  recommend `extra_body={"thinking": {"type": "disabled"}}` for extraction /
  classification / JSON formatting; keep thinking only when the structured
  answer needs hard reasoning. Flash vs Pro: same JSON/tool surface; Flash
  for high-volume extract, Pro for hard reasoning. Synthetic JSON check
  (aireiter, 2026-07-14, thinking-disabled, max_tokens=500): median success
  latency Flash ~8.2 s vs Pro ~8.6 s — and both can still return
  `reasoning_content` / burn budget before final JSON if the endpoint ignores
  disable or `max_tokens` is too tight.
  Evidence: https://api-docs.deepseek.com/quick_start/pricing/ ,
  https://chat-deep.ai/docs/deepseek-thinking-mode/ ,
  https://aireiter.com/blog/deepseek-v4-flash-vs-deepseek-v4-pro .
  Impact: single-pod cold wall is ~20 s/call; Non-think on pass-path JSON is
  a first-class L lever (baseline "decode shrink"), orthogonal to grammar.

- [HIGH] **Guided-decoding latency reports (engine-level, not V4-specific).**
  vLLM blog: Outlines-era sync FSM/mask blocked the batch; XGrammar cut TPOT
  under load up to **~5×** vs that path. SqueezeBits (2025-09, Qwen3 on
  vLLM/SGLang): XGrammar wins on **repetitive simple** schemas (precompute +
  cache); on **unique/complex** schemas, LLGuidance beats XGrammar and
  XGrammar on vLLM can show **erratic throughput stalls** (CPU mask for new
  grammars). vLLM guided path already drops vs unconstrained at concurrency
  ≥8 when mask is not overlapped; SGLang hides more. Red Hat: cached schemas
  on V1 → TPOT only marginally above unconstrained. Youngju (2026-03):
  complex schemas (30+ fields, 4-level nest, heavy regex) → Outlines FSM
  index build **>60 s timeout**; "usually negligible, >10% when deep/large."
  Antigravity production note: nesting past ~4 levels → **3–10×** slowdown;
  pre-warming schema cache cut cold p99 **3–5×**.
  Evidence: https://vllm.ai/blog/2025-01-14-struct-decode-intro ,
  https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang ,
  https://www.youngju.dev/blog/llm/2026-03-07-llm-structured-output-constrained-decoding-json-schema.en ,
  https://antigravitylab.net/en/articles/agents/antigravity-gemma4-constrained-decoding-production-guide .
  Impact: at alliance-pod `--max-num-seqs 16`, a fat Pydantic → guided JSON
  path taxes **all** in-flight decode if compile/mask stalls. Short unit-check
  pass (~55–77 tok) amortizes compile poorly → prefer slim pass schema or
  keep prompt+parse without server guidance.

- [HIGH] **Unsupported / fancy JSON-Schema keywords force the slow path.**
  vLLM `#12201` lineage: `minItems`/`maxItems`, `uniqueItems`, regex
  `pattern` / `patternProperties`, numeric ranges historically weak or
  Outlines-fallback under XGrammar. pydantic `max_length` on lists and
  `ge`/`le` on numbers are exactly those keywords. Anthropic structured-
  output issue `#1185`: compilers often **inline `$ref`/`$defs`**, so DRY
  refs do not shrink compiled grammar; nullable unions
  (`["string","null"]`) inflate grammar size.
  Evidence: https://github.com/vllm-project/vllm/issues/12201 ,
  https://github.com/anthropics/anthropic-sdk-python/issues/1185 .
  Impact: slim the **served** schema (drop bounds/patterns); keep Pydantic
  validators / `ModelRetry` after parse (D6/D10). Avoid "richer schema =
  better" when enabling guided decode on MoE.

- [HIGH] **pydantic-ai / Pydantic mapping.**
  Default pydantic-ai structured path uses **tool calling**; multiple
  output types → separate tools to reduce per-schema complexity. Native
  structured output only when the model profile advertises it. Production
  pattern across guides: Level-2 JSON mode + Level-3 client Pydantic is the
  floor when provider lacks strict `json_schema` (DeepSeek final message).
  Retry loops that echo full `ValidationError.input` bloat tokens
  (pydantic-ai `#4919`). HN/practical consensus: keep Pydantic models
  **flat**, few enums, help the model in the system prompt.
  Evidence: https://pydantic.dev/docs/ai/core-concepts/output/ ,
  https://github.com/pydantic/pydantic-ai/issues/4919 ,
  https://news.ycombinator.com/item?id=46345333 ,
  https://hassanr.com/blogs/llm-structured-output-production-nextjs-python.html .
  Impact: for V4-Pro pod, continue `output_type=<Model>` + retries; if
  turning on server guided JSON, ship **stable small models**, not
  per-call mutated schemas.

- [MED] **When guidance is cheap vs when to drop it.**
  Cheap: same simple JSON schema, grammar cache hot, longer structured gens,
  XGrammar + overlapped mask (SGLang / modern V1). Drop **server** guidance
  (keep client D6): ultra-short classification with high unconstrained
  compliance (~90–94% SqueezeBits Github_easy), MoE repetition/whitespace
  stalls under tight masks, or TTFT/compile dominating <64-token pass calls.
  Friendli note: `response_format` can **raise** throughput with speculative
  decoding (draft accept↑) — guidance is not always a tax on long gens.
  Impact: pass-path → slim or no guidance; defect/monolith nested lists →
  keep structure + cache-friendly schema.

---

## False-pass hypothesis

Treating "we use Pydantic `output_type`" as "we already pay XGrammar cost"
(false: `VllmThinkingBackend` is schema-in-prompt today), or assuming
hosted V4 `json_object` equals OpenAI-style constrained `json_schema`.
Also: slimming by deleting `verdict`/`confidence`/top-level `reasoning`
(prior determinism guardian: fewer free axes can **raise** rerun variance).

---

## Schema-slim tactics (community-validated)

Ordered by how often independent sources agree. Each item is a **tactic**,
not a local patch list.

| # | Tactic | Why (community) | Sources |
|---|--------|-----------------|--------|
| 1 | **Bifurcate pass vs findings schemas** | Tiny repetitive schema stays on XGrammar near-zero path; nested defect arrays never compile for ~70% zero-defect calls | SqueezeBits; 05i; 62; youngju "minimize fields" |
| 2 | **Cap nesting ≤2–3; flatten arrays-of-objects** | Depth >3–4 → FSM/PDA state blowup (cited 3–10× / timeouts at 4+ levels + 30 fields) | Antigravity; youngju; Neural Base; XGrammar nested-CFG paper |
| 3 | **Enum-harden free strings; prefer `guided_choice` for pure labels** | Closed enums shrink context-dependent masks; `guided_choice` claimed **2–3×** faster than JSON-with-enum for classification | youngju; Neural Base Outlines notes; HN flat-schema advice |
| 4 | **Drop grammar bounds (`minItems`/`maxItems`/`ge`/`le`/`pattern`); post-validate** | Those keywords historically leave XGrammar → Outlines or silent ignore | vLLM #12201; 62; hassanr "move business rules out of schema" |
| 5 | **`additionalProperties: false` / XGrammar `strict_mode=True`** | Stops token waste on speculative extra keys; strict mode = unevaluatedProperties/Items false | Antigravity (+10–20 tok); XGrammar docs |
| 6 | **Minimize optional / nullable unions** | `T \| null` and large `anyOf` inflate compiled grammars; order of `anyOf` matters | Anthropic #1185; Neural Base anyOf note; youngju Optional caution |
| 7 | **Fix schema set + prewarm cache** | Unique schema every request kills XGrammar cache; prewarm cut cold p99 3–5× | SqueezeBits; Antigravity; Red Hat V1 cached |
| 8 | **Do not rely on `$ref`/`$defs` to shrink grammar** | Compilers often inline; JSON size ≠ grammar size | Anthropic #1185 |
| 9 | **Split unions into separate output tools / multi-turn fill** | pydantic-ai default; "outer shape then nest" beats one giant schema | pydantic-ai Output docs; Antigravity; Anthropic decomposition |
| 10 | **Shrink enum cardinality; omit low-signal free-text leaves** | 3-way enum ≪ 20-way FSM; drop per-item reasoning/location from structure when one top-level reasoning suffices | Antigravity; 62 Tactic C |
| 11 | **Compact example shape in prompt (hosted `json_object`)** | DeepSeek docs: example keys/types, not a novel full JSON Schema dump; forbid Markdown fences | Official JSON Output guide; chat-deep.ai |
| 12 | **Disable V4 thinking on extract/JSON routes** | Thinking tokens eat `max_tokens` and wall before final JSON | DeepSeek thinking guides; aireiter JSON check |
| 13 | **Pin guided backend; avoid silent Outlines fallback** | One fancy keyword reintroduces batch-blocking FSM tax | vLLM auto-fallback docs; dreaming.press comparison |
| 14 | **Cap prompt-side string length; keep client retries lean** | Prefer "≤N words" in prompt over `maxLength` in grammar; strip fat ValidationError payloads on retry | 62; pydantic-ai #4919 |

### Decision rule (pass-path, single pod)

```
if expected_findings == 0 and output_budget < ~64 tok:
    use SLIM pass schema  # tactics 1, 10, 12
    prefer Non-think
    server guided JSON: optional only if schema cached + A/B clean
elif nested findings required:
    use FULL (or enum-hardened) findings schema  # tactics 3–6
    keep client Pydantic + output_retries
    avoid minItems/pattern/ge in served JSON Schema  # tactic 4
else:  # classification / ternary
    prefer guided_choice or Literal micro-schema  # tactic 3
```

---

## What this does / does not claim for ≤600 s

**Does:** Gives a community-backed slim checklist for L (decode) and for
avoiding guided-decode stalls if/when alliance-pod enables server JSON
schema. Aligns with baseline levers: verdict-first schema, Non-think, Flash
tradeoffs.

**Does not:** Prove schema-slim alone closes the ~800–900 s gap after
MODERATE. Prior envelope math: clean UnitCheck JSON is a small fraction of
~20 s/call wall; grammar complexity and retry avoidance matter more than
raw token count. No dual-pod.

---

## Sources

1. https://api-docs.deepseek.com/guides/json_mode/
2. https://api-docs.deepseek.com/api/create-chat-completion/
3. https://api-docs.deepseek.com/quick_start/pricing/
4. https://chat-deep.ai/docs/deepseek-thinking-mode/
5. https://chat-deep.ai/docs/json-output/
6. https://aireiter.com/blog/deepseek-v4-flash-vs-deepseek-v4-pro
7. https://deepseekai.guide/api/deepseek-api-json-mode/
8. https://vllm.ai/blog/2025-01-14-struct-decode-intro
9. https://blog.squeezebits.com/guided-decoding-performance-vllm-sglang
10. https://dreaming.press/posts/outlines-vs-xgrammar-vs-llguidance.html
11. https://www.youngju.dev/blog/llm/2026-03-07-llm-structured-output-constrained-decoding-json-schema.en
12. https://antigravitylab.net/en/articles/agents/antigravity-gemma4-constrained-decoding-production-guide
13. https://github.com/vllm-project/vllm/issues/12201
14. https://github.com/anthropics/anthropic-sdk-python/issues/1185
15. https://pydantic.dev/docs/ai/core-concepts/output/
16. https://github.com/pydantic/pydantic-ai/issues/4919
17. https://xgrammar.mlc.ai/docs/api/python/grammar_compiler.html
18. Workspace: `research/cold-run-10min/05i-web-guided-decoding-cost.md`,
    `research/cold-run-10min/62-schema-slim-web.md`
