# 05y — Web: CN forums on DeepSeek-V4-Pro vLLM latency (thinking tax + JSON)

**Query:** Zhihu / V2EX / GitHub (+ CN cloud docs that surface in those threads)
for production latency tips on DeepSeek-V4-Pro under vLLM, especially
**thinking tax** and **JSON / structured output** workarounds.

**Date:** 2026-07-24  
**Corpus constraint:** single `alliance-pod` (V4-Pro). No twin Pro pod.  
**Sibling Western notes:** `05-web-think-off-official.md`, `05b-web-flash-vs-pro.md`,
`05v-web-batch-invariant.md`, `16-server-ops-1pod.md`.

---

## Scope / source quality

| Tier | Sources | Trust |
|------|---------|-------|
| A | Tencent TokenHub DeepSeek guide; Infini-AI GenStudio thinking tutorial; vLLM issues/PRs | High (vendor / engine) |
| B | Zhihu practitioner essays; V2EX threads; Tencent Cloud v0.22 writeup | Medium (ops anecdotes) |
| C | CSDN “production deploy” posts with neat tables (expert warmup 4.2s, P99 exact ms, etc.) | **Low** — treat as SEO/LLM spam unless independently reproduced |

Zhihu/V2EX have **almost no measured self-hosted V4-Pro P99** under continuous batching.
Most latency talk is hosted API (official vs 火山) or Flash vs Pro product feel.
Hard engine bugs and workarounds live on **GitHub** and **CN cloud provider docs**.

---

## Findings (latency / thinking / JSON)

### 1. Thinking tax is the default; CN clouds treat Non-think as the structured default

- V4-Flash / V4-Pro: thinking **on by default**; switch via `thinking.type`, not a second model ID.
- TokenHub JSON examples always pair `response_format: json_object` with
  `thinking: {"type": "disabled"}`.
- Best-practice table: simple Q&A → `disabled`; math/logic → `enabled`.
- **Limit (explicit):** 不建议同时开启 `thinking.type=enabled` 与
  `response_format.type=json_object`.
- Thinking on → prefer `stream=true` to avoid gateway timeouts (thinking shares
  `max_tokens` with the answer; TokenHub recommends ≥2048 when thinking).

Evidence: [TokenHub DeepSeek 调用指南](https://cloud.tencent.com/document/product/1823/132248)
(updated 2026-06-26).

vLLM client mapping (already in `05-web-think-off-official.md`):
`extra_body={"chat_template_kwargs": {"enable_thinking": False}}` or
`reasoning_effort="none"` (version-dependent). Infini-AI adds: for hosted
OpenAI-compat paths prefer native `thinking.type`; treat `enable_thinking` as
compat-only after probe.

### 2. Parameter conflict: disabled thinking + reasoning_effort → 400

Infini-AI / CN agent posts: if `thinking.type=disabled`, **do not also send**
`reasoning_effort`. Hosted APIs return 400-style conflicts
(`thinking options type cannot be disabled when reasoning_effort`).

Impact for us: alliance-pod client must send **one** of {think-off, effort},
not both. Re-probe that our pydantic-ai / `AgentBackend` path does not inject
`reasoning_effort=high` while we try Non-think.

Evidence: [Infini-AI DeepSeek thinking 教程](https://docs.infini-ai.com/gen-studio/api/text-generation/tutorial-reasoning/deepseek.html).

### 3. GitHub: thinking + `json_object` dumps JSON into `reasoning` / empty `content`

[vllm#41132](https://github.com/vllm-project/vllm/issues/41132) (closed, DSv4):
with `--reasoning-parser deepseek_v4` + `enable_thinking: True` +
`response_format: json_object`, completion lands in `message.reasoning` and
`content=None`. Fix class: [PR #41199](https://github.com/vllm-project/vllm/pull/41199)
(pass reasoning parser kwargs into structured output). Related streaming
boundary: [vllm#43933](https://github.com/vllm-project/vllm/issues/43933)
(same delta may contain both `reasoning_content` and `content`).

**Workarounds (production):**

1. **Preferred for judge/JSON:** Non-think (`enable_thinking: false` /
   `thinking.type=disabled`) + guided JSON / `json_object`.
2. If thinking must stay on: ensure image includes #41199-class fix; parse
   fallback from `reasoning`/`reasoning_content` when `content` is null;
   raise `max_tokens` so reasoning does not steal the answer budget
   (`finish_reason=length` → discard, do not parse).
3. Infini-AI: **do not enable thinking to “fix” schema failures**; thinking
   does not enforce schema. Flash structured compliance can be intermittent
   even on `stop` — always client-validate.

### 4. Zhihu: for rule-extraction / checklist work, Flash Non-think can beat Pro

[知乎 · Pro 并不比 Flash 好](https://www.zhihu.com/tardis/jm/art/2044020371876209747):
on rule extraction from SOPs / CLAUDE.md-style files, Flash stays literal;
Pro invents rules, writes longer, is slower. Pro wins on open-ended synthesis.

Relevance: our unit checks are closer to **rule / defect checklist JSON** than
agentic synthesis → CN practitioner signal aligns with routing short structured
verdicts off Pro (Flash or dense), not “always Pro because smarter.”

### 5. V2EX: perceived latency often is gateway / harness, not decode

- [V2EX t/1209150](https://www.v2ex.com/t/1209150): official DeepSeek API
  “明显比火山慢”; replies push Flash for speed.
- [V2EX t/1215075](https://www.v2ex.com/t/1215075): Claude Code + DeepSeek
  feels slow; Zed + same API feels fast → **client harness**, not model.
- [V2EX t/1208217](https://www.v2ex.com/t/1208217) folklore: “deepseek 不开放
  推理框架，vllm 效率低” — outdated vs vLLM ≥0.22 production packaging
  ([腾讯云 v0.22 文](https://cloud.tencent.com/developer/article/2680135):
  first “可认真上生产” cut; Cutlass FP8 BI path claims ~28.9% e2e latency
  improvement — see also `05v-web-batch-invariant.md` for why BI is still the
  wrong lever for our fleet).

### 6. CN deploy recipe: clamp `--max-model-len` off the 1M default

[知乎 Flash 本地部署](https://zhuanlan.zhihu.com/p/2045042506988090926):
`--max-model-len 128000` so 1M default does not OOM / starve KV; ModelScope
for mainland download; EP on multi-GPU. Same recipe shape as Western vLLM
blogs, but the **explicit “1M default is a footgun”** warning is louder in CN
hardware-vendor posts.

### 7. Ascend / CN fork: compressed KV → prefix cache is 16K-block shaped

[vllm-ascend#10440](https://github.com/vllm-project/vllm-ascend/issues/10440):
DSv4 compressed MLA — one physical block ≈ **16K tokens**; prompts shorter
than a full block get **0** prefix hits unless partial-hit path is enabled.
[vllm-ascend#9247](https://github.com/vllm-project/vllm-ascend/issues/9247):
MTP can truncate a 32K hit down to 16K via LCM alignment.

Alliance is NVIDIA H200, not Ascend — but if hybrid compressed KV layout
exists on mainline NVIDIA path with large effective block LCM, **short judge
prompts may silently miss APC**. Worth verifying `cached_tokens` on alliance-pod
under MTP (ties to `05d` / `16-server-ops`).

### 8. TokenHub capacity note (hosted, still useful signal)

TokenHub best-practice table: Flash concurrency ceiling **2500** vs Pro **500**
on their gateway. Reinforces Flash for high-QPS structured work; not a
self-host number.

### 9. Multi-turn: chat vs tool-call disagree on echoing `reasoning_content`

| Context | CN guidance |
|---------|-------------|
| Ordinary multi-turn chat | TokenHub: **only** echo `content` (saves tokens) |
| After tool_calls | Infini-AI: **must keep** real `reasoning_content`; never invent `""` |

Western docs often mention one or the other; CN provider docs spell the split.
Our dissect/judge path is mostly single-shot structured, so low impact unless
tool loops are added.

---

## Workarounds cheat-sheet (thinking tax + JSON)

| Goal | Action |
|------|--------|
| Kill thinking tax | `thinking: {type: disabled}` **or** `enable_thinking: false` / `reasoning_effort: none`; never combine disabled + effort |
| Stable JSON | Non-think + `json_object` / guided JSON; put the word “json” + schema in prompt; client-validate |
| Thinking + JSON broken | Upgrade past #41199; or parse `reasoning*` fallback; or turn thinking off |
| Avoid empty JSON | Check `finish_reason`; raise `max_tokens` if reasoning ate budget |
| Latency feel on hosted | Prefer Flash / regional gateway (火山等); measure server `usage` not IDE TTFT |
| Self-host mem/latency | Cap `--max-model-len`; `--kv-cache-dtype fp8`; `--block-size 256`; `--reasoning-parser deepseek_v4`; vLLM ≥0.22 for Pro |
| APC surprises | Log `cached_tokens`; watch MTP × hybrid block LCM (16K-class) |

---

## Tips **not** already covered in our Western forage notes

Western siblings already cover: official think-off knobs, Flash vs Pro speed/quality
trade, BI latency claims, MTP/JSON version sensitivity, server flag checklist.

**CN / forum-only (or much sharper there) additions:**

1. **Hard product limit wording:** TokenHub forbids recommending
   `thinking.enabled` + `json_object` together (not just “Non-think is nicer”).
2. **400 on `disabled` + `reasoning_effort`:** treat as a client invariant;
   Western notes mention think-off but not this conflict.
3. **Do not turn thinking on to repair schema failures** (Infini-AI); schema
   failures need retries / prompt / guided decoding, not more CoT.
4. **Flash can be *better* than Pro on rule-literal JSON tasks** (Zhihu) —
   quality argument for offloading unit checks, not only tok/s.
5. **Harness vs model:** V2EX Claude Code vs Zed on the same DeepSeek key —
   instrument HTTP wall, not agent UI.
6. **Official API vs 火山:** China-path gateway latency is a first-class
   complaint; irrelevant to self-host RunPod but useful when comparing
   published “API latency” anecdotes to pod numbers.
7. **Chat ≠ tools for `reasoning_content` echo** (TokenHub vs Infini-AI split).
8. **Compressed-KV 16K prefix-block / MTP truncation** documented in
   **vllm-ascend** issues — Western NVIDIA recipes rarely state the short-prompt
   APC miss; validate on our image.
9. **TokenHub Flash vs Pro concurrency caps (2500 vs 500)** as a product
   signal that Pro is provisioned as scarce capacity even on CN clouds.

**Ignore / do not act on without measurement:** CSDN claims of “16 dummy
expert warmups,” exact P99 ms tables, fake `--disable-thought` / `fast_tool_dispatch`
flags.

---

## Relevance to ≤10 min single-pod cold run

| Lever | Moves |
|-------|-------|
| Enforce Non-think on all structured UnitCheck calls | Cuts **L** (thinking tokens + parser bugs / retries) |
| Never pair think-on with `json_object` | Cuts retry waste masquerading as “slow pod” |
| A/B Flash or dense for rule-literal checks | Cuts **L** and possibly N if quality holds (see `05b`, `12`) |
| Verify APC `cached_tokens` under MTP | Prefill waste if compressed-block LCM bites |
| Client: no `reasoning_effort` when disabling think | Avoid silent 400 / fallback-to-think paths |

Does **not** by itself close the ~800–900 s gap after MODERATE; it is a
correctness + per-call **L** hygiene pack that Western blogs under-specify.

---

## Sources

1. https://cloud.tencent.com/document/product/1823/132248 — TokenHub DeepSeek guide (think/JSON limits)
2. https://docs.infini-ai.com/gen-studio/api/text-generation/tutorial-reasoning/deepseek.html — Infini-AI thinking + structured
3. https://github.com/vllm-project/vllm/issues/41132 — JSON in `reasoning` when thinking on
4. https://github.com/vllm-project/vllm/pull/41199 — reasoning parser kwargs → structured output
5. https://github.com/vllm-project/vllm/issues/43933 — streaming dual-field delta
6. https://www.zhihu.com/tardis/jm/art/2044020371876209747 — Flash vs Pro rule-following
7. https://zhuanlan.zhihu.com/p/2045042506988090926 — Flash deploy / max-model-len footgun
8. https://zhuanlan.zhihu.com/p/2031073148255351620 — V4 API launch (Flash latency positioning)
9. https://www.v2ex.com/t/1209150 — official vs 火山 latency
10. https://www.v2ex.com/t/1215075 — Claude Code vs Zed perceived latency
11. https://cloud.tencent.com/developer/article/2680135 — vLLM 0.22 DSv4 production packaging
12. https://github.com/vllm-project/vllm-ascend/issues/10440 — 16K compressed prefix blocks
13. https://github.com/vllm-project/vllm-ascend/issues/9247 — MTP truncates prefix hits
