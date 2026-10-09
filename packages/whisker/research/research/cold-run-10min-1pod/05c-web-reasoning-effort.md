# 05c — Web forage: DeepSeek V4 `reasoning_effort` / `thinking` vs decode + latency

**Query:** Impact of DeepSeek V4 `reasoning_effort` (`low` / `high` / `max`) and
`chat_template_kwargs.thinking=false` (Non-think) on decode tokens and wall
latency. Official docs + community. Goal: concrete API knobs for shorter
unit-check decode on **vLLM** (`alliance-pod`).

**Scope:** 2026 web sources fetched 2026-07-24. Evidence cards only; no
fleet-wall math beyond what sources measure.

**Related (cite, do not rediscover):** `research/cold-run-10min/59-deepseek-v4-release.md`
(hosted Non-think dial); `research/cold-run-10min/05a-web-deepseek-vllm.md`
(serving recipe).

---

## Finding cards

### 1. Official V4 modes are three: Non-think / Think High / Think Max (no native `low`)

- **Title:** DeepSeek-V4-Flash / Pro HuggingFace README — Reasoning Mode table
- **URL:** https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash (same table on Pro)
- **Summary:** Instruct cards document exactly three modes:

  | Mode | Characteristics | Response shape |
  |------|-----------------|----------------|
  | Non-think | Fast, intuitive; routine / low-risk | Immediate `</think>` then summary |
  | Think High | Slower, more accurate; complex solving | `<think>…</think>` then summary |
  | Think Max | Fullest effort | Special system prefix + long `<think>` + summary |

  Local tip: `temperature=1.0, top_p=1.0`; Think Max needs context **≥384K**.
- **Relevance:** CRITICAL
- **Conflict note:** OpenAI-style `low` / `medium` are **not** first-class V4
  modes on the HF card. See card 4 for vLLM mapping traps.

### 2. Hosted API knobs: `thinking.type` + `reasoning_effort` high|max

- **Title:** DeepSeek API — Your First API Call
- **URL:** https://api-docs.deepseek.com/ (also `/guides/reasoning_model`)
- **Summary:** Example curl for `deepseek-v4-pro` uses
  `"thinking": {"type": "enabled"}` and `"reasoning_effort": "high"`.
  Legacy `deepseek-chat` / `deepseek-reasoner` retire 2026-07-24 15:59 UTC and
  map to V4-Flash **non-thinking** / **thinking**. Deep Code settings doc
  lists `reasoningEffort` as `"max"` or `"high"` only
  (https://api-docs.deepseek.com/quick_start/agent_integrations/deepcode/).
  Third-party API guides (deepseekai.guide) match: Non-think =
  `thinking: {"type": "disabled"}`; default thinking = high; max = Think Max.
- **Relevance:** HIGH (hosted wire format; self-host uses different kwargs)

### 3. vLLM recipe: put controls in `chat_template_kwargs` (`thinking` + `reasoning_effort`)

- **Title:** deepseek-ai/DeepSeek-V4-Flash | vLLM Recipes (same on Pro)
- **URL:** https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash
- **Summary:** Recipe exposes the same three modes and says: keep reasoning
  controls in `chat_template_kwargs` because Think Max uses
  `"reasoning_effort": "max"`.

  ```python
  # Non-think — omit kwargs (recipe example)
  client.chat.completions.create(model=model, messages=messages)

  # Think High
  extra_body={"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}}

  # Think Max  (needs --max-model-len >= 393216)
  extra_body={"chat_template_kwargs": {"thinking": True, "reasoning_effort": "max"}}
  ```

  Server must use `--tokenizer-mode deepseek_v4` and
  `--reasoning-parser deepseek_v4`.
- **Relevance:** CRITICAL for alliance-pod clients

### 4. `reasoning_effort="low"` on DSV4 does **not** shorten CoT — maps to `high`

- **Title:** [DSV4] Support `max` reasoning effort (vLLM PR #40982, merged)
- **URL:** https://github.com/vllm-project/vllm/pull/40982
- **Summary:** Top-level Chat Completions `reasoning_effort` accepts
  model-specific `"max"`. DeepSeek V4 compatibility mapping:

  | Client value | DSV4 behavior |
  |--------------|---------------|
  | `low`, `medium`, `minimal`, other fallbacks | → **`high`** |
  | `xhigh` | → **`max`** |
  | `none` | disables thinking |
  | `high` / `max` | as named |

  So asking for `"low"` expecting fewer reasoning tokens is a **no-op toward
  High**, not a short-decode path.
- **Relevance:** CRITICAL (anti-pattern for unit-check latency)

### 5. vLLM auto-injection: top-level `reasoning_effort` toggles `enable_thinking`

- **Title:** Reasoning Outputs — Automatic `enable_thinking` Activation
- **URL:** https://docs.vllm.ai/en/stable/features/reasoning_outputs/
- **Summary:** DeepSeek-V4-Pro is called out as requiring
  `enable_thinking: true` in chat-template kwargs to activate thinking;
  without it, reasoning tokens are never generated. When top-level
  `reasoning_effort` is set:

  - `low` / `medium` / `high` → inject `enable_thinking=true`
  - `none` → inject `enable_thinking=false`
  - unset → no injection (preserves default / server default)

  Explicit `chat_template_kwargs.enable_thinking` wins over injection.
  Separate lever: `thinking_token_budget` caps reasoning tokens then forces
  the end-of-think marker (DeepSeek listed among supported families; prior
  tapetum notes say some pods ignore this — verify live).
- **Relevance:** HIGH

### 6. `thinking` vs `enable_thinking`: both accepted; explicit `false` required to disable when default-on

- **Title:** Adapt old `enable_thinking` in chat_template_kwargs (vLLM PR #30852);
  semantic-router #858
- **URL:** https://github.com/vllm-project/vllm/pull/30852 ;
  https://github.com/vllm-project/semantic-router/issues/858
- **Summary:** vLLM treats `thinking` and `enable_thinking` as aliases for
  backward compatibility. Community router bug: clearing the field when
  `use_reasoning=false` fails for Qwen3/DeepSeek because **omitting the flag
  does not disable** models that think by default — must inject
  `enable_thinking: false` or `thinking: false`. V4-Pro on vLLM is documented
  as needing explicit enable for thinking (card 5), while **hosted** DeepSeek
  API defaults thinking **on** (card 2). Clients must know which endpoint they
  hit.
- **Relevance:** HIGH

### 7. Encoding: Max injects a long “absolute maximum” system prefix (more prefill + longer CoT)

- **Title:** DeepSeek-V4 encoding README — Reasoning Effort
- **URL:** https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash/blob/main/encoding/README.md
- **Summary:** `reasoning_effort="max"` prepends a multi-sentence instruction
  (“Absolute maximum with no shortcuts… write out entire deliberation…”)
  before the system message. Non-think / chat mode places `</think>`
  immediately after `<｜Assistant｜>` so the model emits answer tokens only.
  Think High opens `<think>` and expects a full reasoning block before
  content.
- **Relevance:** HIGH (explains why Max is strictly worse for unit-check
  decode *and* adds prompt tokens)

### 8. Community latency: Non-think ~12× faster on classifier-shaped non-stream call

- **Title:** [BUG] deepseek-v4-pro non-streaming classifier timeout from default thinking (#1464)
- **URL:** https://github.com/deepseek-ai/DeepSeek-V3/issues/1464
- **Summary:** Measured on **hosted** `deepseek-v4-pro`, Anthropic-compatible,
  `stream:false`, classifier-shaped ~2.9K-input payload:

  | Condition | Wall | Notes |
  |-----------|-----:|-------|
  | Default thinking (no `thinking` field) | **31.8 s** | TTFB ≈ full reasoning time |
  | Same + `thinking: {"type":"disabled"}` | **2.7 s** | Correct BLOCK verdict; `blocks=[text]` |
  | Heavy-reasoning prompt, thinking on | **86.3 s** | 5638 output tokens |

  Author framing: Non-stream + thinking-enabled ⇒ TTFB = full CoT decode;
  disable thinking for latency-sensitive verdicts. Maintainer ack recorded in
  June 2026 digest.
- **Relevance:** CRITICAL (best public latency delta for “verdict-like”
  structured calls — same class as unit checks)

### 9. Quality cliff Non-think → High → Max is large on hard STEM (official table)

- **Title:** HF Instruct “Comparison across Modes” table
- **URL:** https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro
- **Summary:** Selected V4-Pro rows (Pass@1 / EM):

  | Benchmark | Non-Think | High | Max |
  |-----------|----------:|-----:|----:|
  | GPQA Diamond | 72.9 | 89.1 | 90.1 |
  | HLE | 7.7 | 34.5 | 37.7 |
  | LiveCodeBench | 56.8 | 89.8 | 93.5 |
  | HMMT 2026 Feb | 31.7 | 94.0 | 95.2 |

  High→Max gains are smaller than Non-think→High. Non-think is the decode
  win; Max is almost never the right unit-check mode.
- **Relevance:** HIGH (quality risk if unit checks go Non-think without A/B)

### 10. Secondary: thinking billed as output; migration trap doubles tokens

- **Title:** DeepSeek legacy model retirement / migration catch (TECHi);
  deepseekai.guide performance review
- **URL:** https://www.techi.com/deepseek-chat-reasoner-retirement-v4-migration/ ;
  https://deepseekai.guide/reviews/deepseek-performance-review/
- **Summary:** Hosted thinking returns `reasoning_content`; those tokens are
  **output-billed**. Blind rename `deepseek-chat` → `deepseek-v4-flash` turns
  thinking on and can balloon ~200 → 1000+ output tokens. Flash review cites
  ~83.7 tok/s / ~1.03s TTFT; Pro in max-effort thinking ~42–55 tok/s.
  Guidance: turn thinking off for classification / extraction.
- **Relevance:** MED (cost + decode length; Flash vs Pro is a separate lever)

---

## Cross-cutting: what actually shortens decode

| Knob | Shortens decode? | Notes |
|------|------------------|-------|
| `thinking: false` / `enable_thinking: false` / `reasoning_effort: "none"` | **Yes** (primary) | Non-think; no CoT tokens |
| `reasoning_effort: "low"` | **No** on DSV4 | Maps to High (PR #40982) |
| `reasoning_effort: "high"` | Baseline CoT | Default think depth |
| `reasoning_effort: "max"` | **Lengthens** | Extra system prefix + longest CoT; needs 384K |
| `thinking_token_budget: N` | Caps CoT if honored | Soft truncate of think block; verify on pod |
| Tight `max_tokens` | Caps **total** generation | Cuts answer+think together; risk truncate JSON |
| Hosted `thinking: {"type":"disabled"}` | Yes on api.deepseek.com | Different wire shape than vLLM |

---

## Concrete API knobs for shorter unit-check decode on vLLM

Prefer **request-level** Non-think (do not rely on omit-kwargs alone if any
server default or prior client path enables thinking).

### A. Primary (shortest decode) — Non-think

```python
# Preferred explicit disable (alias either key)
extra_body={
    "chat_template_kwargs": {
        "thinking": False,          # recipe key
        # or: "enable_thinking": False,  # also accepted
    },
}

# Equivalent top-level (auto-injects enable_thinking=false)
reasoning_effort="none"
```

OpenAI SDK shape:

```python
client.chat.completions.create(
    model=model,
    messages=messages,
    max_tokens=unit_check_cap,  # keep tight for JSON verdicts
    extra_body={
        "chat_template_kwargs": {"thinking": False},
    },
)
```

### B. Do **not** use for “lighter thinking”

```python
reasoning_effort="low"   # → High on DSV4; burns CoT as High
reasoning_effort="max"   # longest CoT + Max system prefix
```

### C. If thinking must stay on (quality holdout)

```python
extra_body={
    "chat_template_kwargs": {
        "thinking": True,
        "reasoning_effort": "high",  # never max for unit checks
    },
    "thinking_token_budget": N,     # only if live pod honors it
}
```

### D. Hosted DeepSeek API (not alliance-pod)

```json
{"thinking": {"type": "disabled"}}
```

Do not send vLLM-only `chat_template_kwargs` expecting the same effect on
`api.deepseek.com`.

### E. Server assist (optional)

```bash
# If the pod defaults thinking on for some models:
--default-chat-template-kwargs '{"thinking": false}'
# Request-level kwargs still override.
```

---

## Takeaway for cold-run ≤10 min / 1 pod

1. **Only Non-think is a first-class short-decode dial** among the effort
   strings people confuse with “low/medium/high.”
2. **`low` is a trap on DSV4** (aliases High).
3. Community classifier measurement: **~31.8 s → ~2.7 s** by disabling
   thinking on a verdict-shaped non-stream call — order-of-magnitude decode
   win, quality A/B still required for tapetum unit checks (HF Non-think
   cliffs on hard STEM).
4. Pair Non-think with existing tight `max_tokens` / verdict-first schema;
   Max and `low` are not useful knobs for this workload.
