# Official DeepSeek V4 think-off (foraged 2026-07-24)

**API (hosted DeepSeek):**
```python
extra_body={"thinking": {"type": "disabled"}}
```
Default on V4 is thinking **on** (`reasoning_effort` high). Non-thinking is the recommended path for extraction / structured / latency-sensitive work.

**vLLM mapping (verify against alliance-pod image):**
```python
extra_body={"chat_template_kwargs": {"enable_thinking": False}}
# or thinking: false / reasoning_effort none per vLLM version
```

**Relevance to us:** Prior live probe (2026-07-07) said alliance-pod ignored `thinking_token_budget` and emitted no hidden reasoning on the production template. That may mean (a) already Non-think, or (b) kwargs not wired. **Must re-probe** with explicit `enable_thinking: false` vs true under structured UnitCheck and measure completion_tokens + wall.

**Flash tier:** V4-Flash is Instant Mode; Pro is Expert. Flash is a model swap, not a flag — only useful if Alliance deploys Flash weights (separate from twin-pod ban).

Sources: deepseekai.guide API docs; chat-deep.ai thinking mode; vLLM recipes.
