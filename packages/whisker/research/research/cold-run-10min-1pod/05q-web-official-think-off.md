# 05q — Official DeepSeek V4 think-off → vLLM `chat_template_kwargs`

**Query:** Official DeepSeek API docs: how to disable thinking for V4; map
that wire format to vLLM `chat_template_kwargs`. Return exact kwargs.

**Scope:** Official `api-docs.deepseek.com` fetched 2026-07-24, plus vLLM
recipe / reasoning-output docs for the self-host mapping. Evidence only; no
fleet-wall math.

**Related (cite, do not rediscover):** `05-web-think-off-official.md` (stub),
`05a-web-nonthink.md` (quality cliffs), `05c-web-reasoning-effort.md` (effort
traps / decode knobs).

---

## Exact answer (copy-paste)

### Hosted DeepSeek API (`api.deepseek.com`)

```json
{"thinking": {"type": "disabled"}}
```

OpenAI Python SDK:

```python
extra_body={"thinking": {"type": "disabled"}}
```

### vLLM OpenAI-compatible (`alliance-pod`)

Exact `chat_template_kwargs` for Non-think (think-off):

```json
{"thinking": false}
```

Alias also accepted by vLLM:

```json
{"enable_thinking": false}
```

Request shapes:

```python
# Preferred explicit Non-think
extra_body={"chat_template_kwargs": {"thinking": False}}

# Alias
extra_body={"chat_template_kwargs": {"enable_thinking": False}}

# Top-level equivalent (vLLM auto-injects enable_thinking=false)
reasoning_effort="none"
```

**Do not** send hosted `{"thinking": {"type": "disabled"}}` to vLLM and expect
the same effect. That object is the hosted API toggle; self-host uses
`chat_template_kwargs`.

---

## Official sources

### 1. Create Chat Completion — `thinking.type`

- **URL:** https://api-docs.deepseek.com/api/create-chat-completion/
- **Fetched:** 2026-07-24
- **Models:** `deepseek-v4-flash`, `deepseek-v4-pro`
- **Field:** `thinking` (object, nullable)
  - Controls switch between thinking and non-thinking mode.
  - Nested `type` string: `enabled` | `disabled`
  - **Default:** `enabled`
  - Docs text: if `enabled` → thinking mode; if `disabled` → non-thinking mode.
- **Effort (separate):** `reasoning_effort` ∈ `high` | `max` (only meaningful
  when thinking is on; `low`/`medium` map to `high`, `xhigh` → `max`).

### 2. Thinking Mode guide — OpenAI / Anthropic table

- **URL:** https://api-docs.deepseek.com/guides/thinking_mode
- **Fetched:** 2026-07-24 (HTML; guide title “Thinking Mode | DeepSeek API Docs”)
- **OpenAI-format toggle:** `{"thinking": {"type": "enabled/disabled"}}`
- **OpenAI-format effort:** `{"reasoning_effort": "high/max"}`
- **Anthropic-format effort:** `{"output_config": {"effort": "high/max"}}`
- Notes from guide:
  1. Thinking toggle **defaults to `enabled`**.
  2. In thinking mode, default effort is `high` for regular requests; some
     complex agent clients get `max` automatically.
  3. Compatibility: `low`/`medium` → `high`; `xhigh` → `max`.
- SDK note: pass `thinking` via `extra_body` with the OpenAI Python SDK.
  Example in guide uses
  `extra_body={"thinking": {"type": "enabled"}}` with
  `reasoning_effort="high"`. Disable by swapping `"type"` to `"disabled"`.

---

## Mapping: hosted API → vLLM

| Intent | Hosted DeepSeek API | vLLM `chat_template_kwargs` | vLLM top-level alt |
|--------|---------------------|-----------------------------|--------------------|
| **Think off (Non-think)** | `{"thinking": {"type": "disabled"}}` | `{"thinking": false}` or `{"enable_thinking": false}` | `reasoning_effort="none"` |
| Think on (High) | `{"thinking": {"type": "enabled"}}` + `reasoning_effort="high"` | `{"thinking": true, "reasoning_effort": "high"}` | `reasoning_effort="high"` (auto-injects enable) |
| Think Max | `{"thinking": {"type": "enabled"}}` + `reasoning_effort="max"` | `{"thinking": true, "reasoning_effort": "max"}` | `reasoning_effort="max"` |

### vLLM recipe corroboration

- **URL:** https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
  (same pattern on Flash)
- Non-think example: bare `chat.completions.create(...)` with **no**
  `chat_template_kwargs` (recipe default path).
- Think High / Max: `extra_body={"chat_template_kwargs": {"thinking": True,
  "reasoning_effort": "high"|"max"}}`.
- Serve flags: `--tokenizer-mode deepseek_v4`, `--reasoning-parser deepseek_v4`.

### vLLM reasoning docs corroboration

- **URL:** https://docs.vllm.ai/en/stable/features/reasoning_outputs/
- DeepSeek-V4-Pro called out as needing `enable_thinking: true` in template
  kwargs to emit reasoning; without it, no reasoning tokens.
- Top-level `reasoning_effort="none"` → injects `enable_thinking=false`.
- Explicit `chat_template_kwargs` wins over auto-injection.
- Server default option: `--default-chat-template-kwargs '{"thinking": false}'`
  (request-level still overrides).

### Encoding semantics (why `thinking: false` means Non-think)

- HF / vLLM DeepSeek-V4 encoding uses `thinking_mode` ∈ `"chat"` | `"thinking"`.
- Non-think (`"chat"`) closes the think block immediately after
  `<｜Assistant｜>` so the model emits content with no CoT.
- vLLM’s boolean `thinking` / `enable_thinking` in `chat_template_kwargs` is
  the OpenAI-compat knob that selects that path; it is **not** the hosted
  nested `thinking.type` object.

---

## Operator takeaway for this corpus

For **explicit** think-off on vLLM (`alliance-pod`), send:

```python
extra_body={"chat_template_kwargs": {"thinking": False}}
```

Exact kwargs object:

```json
{"thinking": false}
```

Prefer explicit `false` over omit-kwargs alone when any server default or
client path may enable thinking. Hosted syntax stays
`{"thinking": {"type": "disabled"}}` and must not be copied onto the pod.
