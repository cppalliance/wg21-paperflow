# INFRA-ASK — Restart `h200-qwen3-32b`

**Audience:** Alliance ops / Slack  
**Date:** 2026-07-24  
**Priority:** Critical for ≤10 min cold-run path (Option B). Without this, honest SLA is ~15–20 min (Option A/C).

---

## Exact ask (copy/paste)

> **Ask:** Please restart the Alliance dense endpoint **`h200-qwen3-32b`** (Qwen3-32B on H200) so it serves OpenAI-compatible `/v1` again.
>
> **Why:** Whisker tapetum cold-run research needs a **live dense judge** to offload ~1500–1800 unit/metadata LLM calls off the shared MoE pod `alliance-pod` (DeepSeek-V4-Pro, S=16). Twin V4-Pro is **not** requested and remains forbidden. Today all dense services in `SERVICES.toml` return **HTTP 404**; only `alliance-pod` is up. Heterogeneous cascade (`wall = max(T_moe, T_dense)`) is **infra-blocked** until at least `h200-qwen3-32b` is healthy.
>
> **Not asking for:** a second DeepSeek-V4-Pro / `h200x8-deepseek-v4-pro`, raising MoE `--max-num-seqs`, or exclusive reservation of `alliance-pod`.
>
> **Nice-to-have later (not blocking this ask):** `b300-qwen36-27b` as reserve after A/B. Please do **not** prioritize `b200x2-gemma4` or `b200-r1` for unit-judge primary.

---

## Why this specific pod

| Reason | Detail |
|--------|--------|
| Primary dense anchor in architecture | Report `12`: ~1502 in-budget unit checks + (unless det-metadata lands) 377 metadata calls |
| Context fit | 131k window covers 373/381 papers; 8 oversize stay on MoE |
| Avoid alternates as primary | Gemma-4: wording false-fail; R1: thinking overhead |
| Only ≤10 min arithmetic path under twin ban | MoE-only floors above 600 s at quality (`17`, `SYNTHESIS`) |

---

## Success criteria (ops + research)

Minimum bar before research treats dense as unblocked:

| Check | Pass |
|-------|------|
| **`GET {base_url}/v1/models`** | **HTTP 200** |
| Response body | Lists expected model id for `h200-qwen3-32b` (match `SERVICES.toml`) |
| Chat smoke (optional but preferred) | One small `chat/completions` returns 200 |
| Stability | Stays up for a full AGGRESSIVE B (~10–12 min) + bench window |

**Probe pattern (research side after ops confirms):**

```bash
# Expect HTTP 200 and a models list; 404 = still blocked
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer $DENSE_KEY" \
  "$H200_QWEN3_32B_BASE/v1/models"
```

Until this returns **200**, Package C / Option B stays **infra-dead**. Policy permission alone is not enough (`26`).

---

## What unblocks after success

1. `vllm bench serve` at 12k/256 and 40k/900 shapes  
2. Payload-scoped cascade pilot  
3. Quality gate bundled B (`19` / `QUALITY-PROTOCOL.md`)  
4. Possible claim of ≤10 min **only if** measured wall_B ≤ 620 s **and** quality tiers pass  

If ops will **not** restart: publish Option C SLA (~15–20 min) and stop the 10-min program.
