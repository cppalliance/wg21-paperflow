# 26 - Server Ops Checklist (alliance-pod vLLM flags)

**Audience:** Sam / RunPod operator  
**Goal:** Cut cold `whisker-tapetum-llm` wall time toward ~10 min without a whisker deploy  
**Baseline:** 3003 s cold run, 2284 LLM calls, 16 server slots, client c=32  
**Sources:** `research/tapetum-llm-speedup/40-server-flag-auditor.md`, `05-web.md`, `15-prefix-cache-enabler.md`, `research/slots-32-regression/15-deployment-tuning.md`, `packages/whisker/research/deepseek-v4-pro/SYNTHESIS.md`, `research/cold-run-10min/12-prefix-cache-code-auditor.md`

**Verdict:** Server flags alone save **~300–550 s** (10–18%) on the 3003 s cold run. They do **not** reach 5–10 min without client levers already in v11 (metadata short-circuit, HMAC tag, prompt reorder). Ops changes require a **pod restart**, not a repo deploy.

---

## What Sam/ops can change without code deploy

| Change class | Examples | Requires |
|---|---|---|
| RunPod template env | `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` | Pod restart |
| vLLM launch flags | MBT, APC, MTP, CUDA graphs, long-prefill threshold, reasoning/tokenizer parsers | Pod restart |
| Container image bump | `cppalliance/vllm-openai:v0.24.0` **with PR #43447** (DeepSeek V4 APC retention merge) | Pod restart + image pull |
| Verification only | `GET /version`, `GET /metrics`, startup log grep | Nothing |

**Not ops-only (needs whisker release):** guard-tag HMAC, user-message reorder, metadata short-circuit, client concurrency, dual-pod sharding, verdict-first schema. v11 already ships PDF-lane tag + reorder + metadata short-circuit at HEAD.

---

## Pre-flight: confirm build before APC work

APC on DeepSeek V4 without the retention fix can stay at **0% hits** and add hash overhead.

| Check | Command / location | Pass |
|---|---|---|
| vLLM build includes PR #43447 | `GET $POD/version` or startup log `vLLM API server version` | Build ≥ 2026-06-04 merge of [PR #43447](https://github.com/vllm-project/vllm/pull/43447) |
| Retention env | RunPod env block or `/server_info` `vllm_env` | `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` |
| Container tag | RunPod template | `cppalliance/vllm-openai:v0.24.0` or newer **verified** to include #43447 |

If build predates #43447: upgrade image first, then enable APC + retention. Do not treat "APC enabled" as optimized until hit rate rises under load.

---

## Operator verification checklist (live pod)

Run after restart and during a fleet load test.

| Flag / knob | How to verify | Pass criterion |
|---|---|---|
| **`--max-num-batched-tokens` (MBT)** | Startup log `max_num_batched_tokens=`; `/server_info` scheduler block | **16384** (recipe default). Absent on H200 OPENAI path ⇒ implicit **8192** on v0.24 |
| **`--enable-prefix-caching` + retention** | Startup `Enabling prefix caching`; `/metrics` `vllm:prefix_cache_hits_total` / `queries_total` | Explicit **on** + `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768`. Interval hit rate > 0% under fleet load |
| **`--tokenizer-mode deepseek_v4`** | Startup log or `/server_info` | Present. Wrong tokenizer ⇒ silent wrong tokens on multi-turn (correctness, not throughput) |
| **`--reasoning-parser deepseek_v4`** | Startup log; smoke: JSON lands in `content` after thinking | Present. Required for thinking + structured JSON paths (#41199 fixed in v0.24) |
| **`--tool-call-parser deepseek_v4`** | Startup log | Present if auto tool choice enabled |
| **`--max-num-seqs`** | `/metrics` `vllm:num_requests_running` peak ≤16; startup log | **16** (measured sweet spot; 32 regressed wall +57%) |
| **`--kv-cache-dtype fp8`** | Startup `kv_cache_dtype=fp8` | **fp8** (already in H200SXM.txt; confirm, not a delta) |
| **MTP / `--speculative-config`** | Startup `SpeculativeConfig(method='mtp'...)` | `{"method":"mtp","num_speculative_tokens":1}` first; A/B k=2 if acceptance metrics justify |
| **CUDA graph mode** | Startup `compilation_config` / `cudagraph_mode` | `{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}` |
| **Chunked prefill** | `/server_info` `chunked_prefill_enabled=True` | **Leave on** (default when model supports) |
| **`--long-prefill-token-threshold`** | Startup log | **8192** (co-tune with MBT 16384) |
| **Scheduler health** | `/metrics`: `num_requests_waiting`, `kv_cache_usage_perc`, TPOT histogram | Waiting ≈ 0 sustained at c=16; no preemption storm |

**Log grep one-liner (pod stdout):**

```text
max_num_batched_tokens|max_num_seqs|prefix caching|SpeculativeConfig|compilation_config|cudagraph|kv_cache_dtype|chunked_prefill|tokenizer-mode|reasoning-parser
```

**Metrics one-liner:**

```bash
curl -s "$POD/metrics" | rg 'prefix_cache|num_requests_(running|waiting)|kv_cache_usage'
```

**Prefix hit rate (during fleet):**

```promql
rate(vllm:prefix_cache_hits_total[5m]) / rate(vllm:prefix_cache_queries_total[5m])
```

Expect rise above 0% once static system prefix + v11 client layout share leading tokens. Document-level hits need identical system prompt **and** reordered user blocks (v11 PDF lane).

---

## Target launch delta (add to H200SXM baseline)

**Keep from current template:** TP8+EP, `--max-num-seqs 16`, `--max-model-len 393216`, `--kv-cache-dtype fp8`, `--gpu-memory-utilization 0.95`, `--enable-ep-weight-filter`.

**Add or replace:**

```bash
# RunPod environment
VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768

# Container start command additions
--max-num-batched-tokens 16384 \
--enable-prefix-caching \
--tokenizer-mode deepseek_v4 \
--reasoning-parser deepseek_v4 \
--tool-call-parser deepseek_v4 \
--speculative-config '{"method":"mtp","num_speculative_tokens":1}' \
--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}' \
--long-prefill-token-threshold 8192
```

**Do not change without full co-tune triangle:**

- `--max-num-seqs` above 16 (MoE decode fan-out regresses wall)
- Disable chunked prefill
- APC without PR #43447 build + retention env

---

## Quality / determinism classification (server flags)

| Lever | Changes model outputs? | Ops action |
|---|---|---|
| MBT 16384 | No (scheduling) | Safe to apply |
| APC + retention env | No (bitwise KV replay) | Safe after #43447 verified |
| MTP k=1 | No (lossless rejection sampling) | A/B if JSON retry rate shifts |
| CUDA graphs FULL_DECODE_ONLY | No | Safe to apply |
| Long-prefill threshold 8192 | No | Safe with MBT 16384 |
| FP8 KV | Slight (already live) | Confirm only |
| tokenizer-mode / reasoning-parser | Correctness gate | Verify present; not a speed lever |

Scheduling-only levers: verdict-identity A/B (byte-diff sidecars) suffices. No full 381-paper semantic revalidation required.

---

## Interaction with client v11 (no ops action)

At HEAD `_LANE_VERSION=11`:

- PDF fleet uses per-paper HMAC guard tag (not per-call random)
- Unit/page checks lead with shared candidate markdown
- Metadata short-circuit removes ~44.6% of unit calls

Server APC + retention unlocks **static system-prefix** hits immediately. **Document payload** hits depend on v11 client layout already deployed. Re-measure cold wall after ops flags + v11 together; do not attribute prefix wins to server flags alone if client is still pre-v11.

---

## Rollout procedure

1. Snapshot current flags from startup log + `/metrics` baseline.
2. Confirm vLLM build ≥ PR #43447; bump image if needed.
3. Apply env + launch delta; restart pod.
4. Smoke: one paper through `whisker-tapetum-llm` with `--trace`; confirm JSON parse, no empty `content`.
5. Run 381-paper cold fleet with `/metrics` scrape every 10 s during load.
6. Compare wall time + sidecar verdict byte-diff vs pre-change baseline.
7. If wall savings < 200 s or verdict diffs exceed advisory flip budget, revert MTP first, then CUDA graphs; keep MBT + retention.

---

## Top 5 server flag changes (cold-run impact rank)

Ranked by **expected savings on the 3003 s cold run**, ops-only, conservative envelopes from `40-server-flag-auditor.md`. Overlap discounted ~25% in the combined bundle.

| Rank | Flag change | Expected cold-run impact | Quality risk | Notes |
|---|---|---|---|---|
| **1** | `--max-num-batched-tokens 16384` | **100–250 s** | None | Largest scheduling-only win. H200SXM omits explicit MBT ⇒ v0.24 defaults 8192. Co-tune with `--max-num-seqs 16`. |
| **2** | `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` | **100–200 s** | Low (monitor JSON retries) | Decode-heavy workload (~5.91 s decode mean). Start k=1; k=2 hurts short OSL. |
| **3** | `--enable-prefix-caching` + `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` (requires #43447) | **60–180 s** server-only | None | Without retention, DeepSeek V4 APC can stay 0% at c=16. v11 client unlocks larger document-prefix wins (code deploy, not ops). |
| **4** | `--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'` | **50–120 s** | None | Recipe CUDA-graph decode path; missing from H200SXM today. |
| **5** | `--long-prefill-token-threshold 8192` | **30–80 s** (incremental vs MBT alone) | None | Co-tune for 3k–100k judge prefills; pair with MBT 16384. |

**Not in top 5 for cold-run wall time (still verify):**

- `--tokenizer-mode deepseek_v4` / `--reasoning-parser deepseek_v4`: **correctness and parse reliability**, not primary throughput levers. Missing or wrong parser ⇒ retries, empty JSON, or hidden reasoning in wrong field (quality failures masquerading as slowness).
- `--kv-cache-dtype fp8`: already deployed; **0 s incremental**.
- Raising `--max-num-seqs`: **negative** (+57% wall at 32).

**Combined server-flag envelope (all five + verify parsers): ~300–550 s → projected wall ~2450–2700 s (~41–45 min)** without client call-count levers. With v11 metadata short-circuit already live, post-ops cold wall should be re-baselined against HEAD, not raw 3003 s.

---

## False-pass / false-fail (operator traps)

**False-pass:** Enable APC on pre-#43447 build; metrics show ~0% hits; team assumes server tuning complete while wall unchanged or slightly worse from APC hash overhead.

**False-fail:** Deploy MTP k=2 (recipe default) on short JSON judge outputs; draft overhead dominates; revert **all** recipe flags including beneficial MBT 16384 and retention env.

---

## References

- Full flag audit: `research/tapetum-llm-speedup/40-server-flag-auditor.md`
- APC retention evidence: `research/tapetum-llm-speedup/05-web.md` Q1, Q4
- Client prefix layout: `research/tapetum-llm-speedup/15-prefix-cache-enabler.md`
- v11 code status: `research/cold-run-10min/12-prefix-cache-code-auditor.md`
- H200 baseline template: `https://raw.githubusercontent.com/cppalliance/runpod/master/templates/deepseek/H200SXM.txt`
- DeepSeek-V4-Pro recipe: `https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro`
