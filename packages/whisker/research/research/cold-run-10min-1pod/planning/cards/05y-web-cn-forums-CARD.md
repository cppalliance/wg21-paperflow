# CARD: 05y — CN forums: V4-Pro thinking tax + JSON

## Bottom line
CN vendor docs sharpen Western think-off notes: Non-think is the structured default; TokenHub explicitly advises against `thinking.enabled` + `json_object`; disabled thinking + `reasoning_effort` → 400. Thinking-on + `json_object` can dump JSON into `reasoning` / empty `content` (vLLM #41132; fix class #41199). Flash can beat Pro on rule-literal checklist JSON.

## Numbers
- TokenHub: Flash concurrency ceiling **2500** vs Pro **500** (hosted signal).
- Thinking shares `max_tokens` with answer; TokenHub recommends ≥**2048** when thinking; stream to avoid gateway timeouts.
- Zhihu Flash local: clamp `--max-model-len` (e.g. **128000**) — 1M default is a footgun.
- vllm-ascend: compressed KV one physical block ≈ **16K tokens** → short prompts can get **0** prefix hits; MTP can truncate 32K hit to 16K via LCM.
- Tencent v0.22 Cutlass FP8 BI path claims ~**28.9%** e2e (still wrong speed lever for this fleet — see 05v).

## Architecture implication
Enforce Non-think on structured UnitCheck; never pair think-on with `json_object` without #41199-class image + parse fallback. Client must send one of {think-off, effort}, not both. Verify `cached_tokens` under MTP for silent APC miss. Instrument HTTP wall, not IDE harness TTFT (V2EX Claude Code vs Zed).

## Reject-or-A-B
- **Ship hygiene:** Non-think + JSON path; no `reasoning_effort` when disabling think; client-validate; check `finish_reason`.
- **A/B:** Flash or dense for rule-literal unit checks (quality, not only tok/s) — aligns with `05b`/`12`.
- **Reject without measure:** CSDN “expert warmup 4.2s / exact P99” SEO tables; fake `--disable-thought` flags.
- **Does not alone** close ~800–900 s gap; L + retry hygiene pack.

## Links
- Source: `05y-web-cn-forums.md`
- Related: `05q-web-official-think-off.md`, `05b-web-flash-vs-pro.md`, `05v-web-batch-invariant.md`, `16-server-ops-1pod.md`
- https://cloud.tencent.com/document/product/1823/132248
- https://docs.infini-ai.com/gen-studio/api/text-generation/tutorial-reasoning/deepseek.html
- https://github.com/vllm-project/vllm/issues/41132 , PR #41199
