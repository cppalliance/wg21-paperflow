# 61 - KV / APC eviction on H200 (DeepSeek MoE MLA)

**Verdict:** usable — APC eviction can cause serial re-prefill under load even
when **lifetime** hit rate looks excellent, but that mechanism does **not**
displace our historical document-prefix killer (random per-call guard +
unit-fields-first layout). At HEAD (v11), the random tag is largely gone on
the PDF fleet path; eviction / hybrid-SWA retention / cross-call-type system
divergence are the residual suspects.
**Confidence:** high (mechanism); medium (our live capacity numbers)

**Date:** 2026-07-24
**Question:** Does APC eviction explain serial re-prefill when lifetime hit
rate looks high? Is the random guard tag still the main APC killer vs eviction?

---

## Findings

- [CRITICAL] **Lifetime token hit rate is the wrong window for "did call 2 reuse
  call 1's document KV".** vLLM exports cumulative counters
  `prefix_cache_hits` / `prefix_cache_queries` (token counts, not blocks;
  PR #18003). Design docs instruct Prometheus
  `rate(hits[5m])/rate(queries[5m])` for interval hit rate; the engine also
  keeps a rolling ~1k-request window for logs
  ([metrics design](https://github.com/vllm-project/vllm/blob/main/docs/design/metrics.md)).
  Our live probe (2026-07-23): **96.66% lifetime** over **131 568** finished
  requests (`146-verifier-prefix-cache-contradiction.md`). That average mixes
  warm reruns, shared system prefixes, and any cold bursts. Impact: high
  lifetime hit rate is compatible with a cold fleet interval where document
  bodies miss and re-prefill. Quality risk: none (observability only).

- [CRITICAL] **Eviction can force re-prefill of a prefix that "just hit" in
  aggregate metrics.** vLLM APC free-queue uses LRU: allocating under pressure
  pops cached blocks from the free-queue head
  (`92-vllm-apc-internals.md`; `docs/design/prefix_caching.md`). Open RFC
  [#48485](https://github.com/vllm-project/vllm/issues/48485) (2026-07-13):
  eviction is **unaware of the waiting queue**, so a cached prefix owned by a
  request near the head of the wait queue can be evicted moments before that
  request is admitted → full recompute / higher TTFT. Impact: under client
  **c=32** vs **16** server slots with many distinct 10–40k papers, in-paper
  serial call *N+1* can miss call *N*'s document blocks even when hash
  identity is perfect. Quality risk: none (time only).

- [CRITICAL] **Random per-call guard was the document-prefix identity killer,
  not eviction — and it is fixed on the PDF fleet path at HEAD.** Pre-v11:
  `SRC{secrets.token_hex(4)}` at system tail broke the block-hash chain from
  token 0 (`92:8`, `15-prefix-cache-enabler`). System-prefix tokens (~900)
  could still hit; the 10–40k `candidate_md` could not be shared across the
  ~6 serial calls. v11 CLI: per-run secret + `_paper_guard_tag` HMAC + unit/page
  reorder (`12-prefix-cache-code-auditor.md`). Impact: for production
  `whisker-tapetum-llm` PDF runs, **random guard is no longer the main APC
  killer**. Residual: library `guard_tag=None` fallback, HTML text lane
  per-run random, different system prompts across call types. Quality risk:
  none for the HMAC swap (149 security model).

- [HIGH] **DeepSeek MoE MLA KV is small per token, but residency under
  concurrency is still tight for 10–40k docs.** External anchors:
  - Classic MLA (V2/V3): cache `(d_c + d_rope) = 512+64` elems/layer ≈
    **~70 KB/token** bf16 across ~61 layers
    ([Aleph Alpha theoretical model](https://aleph-alpha.com/blog-assets/DeepSeek-Inference-Theoretical-Model_Deriving-the-performance-from-hardware-primitives_02092025.pdf);
    ~57× vs MHA).
  - DeepSeek-V4 `fp8_ds_mla` packing: **584 B/storage token**
    (448 NoPE + 128 RoPE + 8 scale; vLLM
    [#47648](https://github.com/vllm-project/vllm/issues/47648) /
    [#47716](https://github.com/vllm-project/vllm/pull/47716)).
  - Alliance-pod live `/metrics`: `cache_dtype=fp8`, `block_size=4`,
    `num_gpu_blocks=17679`, `sliding_window=128`, APC on (`146`).
  - Persona 92 capacity sketch: at **P≈40k**, expect on the order of
    **~10–30** full-paper prefixes if idle, but **~1–3 hot papers** under
    32-way churn without identical prompts; sglang H200 Pro notes also cite
    ~15 concurrent KV-resident requests (`109-sglang-moe-support.md`).
  Impact: MLA makes long docs *fit*; it does **not** make 381 distinct 40k
  prefixes co-resident. Cross-paper reuse stays negligible; in-paper serial
  reuse is the lever, and LRU thrash can steal it. Quality risk: none.

- [HIGH] **Hybrid full-MLA + SWA retention is a second eviction class on
  DeepSeek-V4.** Without selective retention, SWA local checkpoints are
  densely evicted under concurrency → **0% prefix hits** in V4 traces; with
  `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` + PR #43447, replay at c=16
  went **0% → 74.3%** (`05-web.md` Q1; `92:10`). Impact: "APC enabled + high
  lifetime hits" can still mean hybrid-group misses / re-prefill if the
  retention env is missing on the running image. Ops checklist already
  tracks this (`26-server-ops-checklist.md`). Quality risk: none (KV only).

- [HIGH] **High lifetime hits already prove large-prefix reuse *somewhere* —
  so eviction was never the sole story for the 96.66% number.** Probe means:
  **91 823** prompt tokens/req, only **3 068** locally computed (~3.3%)
  (`146`). Pure system-prefix hits (~1k tok) cannot produce that ratio on
  91k prompts. Dominant explanation for the lifetime counter: **warm
  identical reruns / shared long prefixes across the pod's history**, not
  "APC is broken." Tapetum cold serial re-prefill of document bodies was a
  **client hash/layout** problem riding on top of a healthy APC server.
  Impact: do not use eviction as the excuse to skip HMAC/reorder validation;
  do use eviction as the reason interval scrapes can still look bad after
  v11. Quality risk: none.

- [MED] **Partial hits inflate lifetime rate while still forcing heavy
  re-prefill.** APC matches contiguous blocks from token 0; the last prompt
  token is always recomputed; MTP/EAGLE may drop the last matched block
  (`92:20`). A request can show a "hit" on the static system head and miss
  the document tail after a mid-prefix divergence or after LRU ate the long
  tail first. Token-weighted lifetime hit rate stays high; wall-clock prefill
  for the unique suffix stays large. Impact: interval `local_compute` tokens
  and `request_prefill_time_seconds` matter more than hit%. Quality risk: none.

---

## Capacity sketch (10–40k docs on H200 / DSV4 MLA)

| Quantity | Approx | Source |
|---|---|---|
| DSV4 `fp8_ds_mla` | 584 B / storage token | vLLM #47648 / #47716 |
| Classic MLA bf16 (V3-class) | ~70 KB / token | Aleph Alpha model |
| 40k-token document (584 B) | ~23 MB / token-row (before layer packing) | arithmetic |
| Live pod blocks | `num_gpu_blocks=17679`, `block_size=4` | 146 probe |
| Concurrent long seqs (pod policy) | 16 | SERVICES / baseline |
| Client in-flight | 32 | baseline |
| Papers in cold fleet | 381 × ~6 calls | baseline |

Interpretation: MLA compression is why 10–40k judge payloads are viable at
all on one H200 node. Under 16-wide decode + 32-wide client churn, free KV
for **idle cached** prefixes is a small multiple of "one hot paper," not
"the whole fleet." That is enough for **in-paper serial reuse** if hash
identity holds and the next call arrives before LRU reclaims the blocks;
it is **not** enough to treat lifetime hit% as proof that serial reuse
already works during a cold scan.

---

## Does eviction explain "high lifetime hit + serial re-prefill"?

| Claim | Verdict |
|---|---|
| Eviction **can** cause serial re-prefill while lifetime hit% stays high | **Yes** — wrong window + LRU / wait-queue-blind eviction (#48485) + SWA retention |
| Eviction **was** the main reason tapetum re-prefills document bodies while APC showed 96.66% | **No** — identity break (random guard + unit-fields-first) + warm-dominated lifetime mix (`146`, `12`) |
| After v11 HMAC + reorder, eviction becomes a **plausible residual** for missed in-paper hits | **Yes** — especially cold 381-paper bursts at c=32 without retention env |

---

## Answer: random guard vs eviction (today)

**Random per-call guard tag is no longer the main APC killer on the
production PDF fleet path** (v11 HMAC + reorder landed; see
`12-prefix-cache-code-auditor.md`).

**Eviction was never the better explanation for the historical
contradiction** (96.66% lifetime vs full document re-prefill). That was
client prompt identity / layout, with lifetime counters dominated by warm /
shared long prefixes.

**Eviction is now a first-class co-suspect for post-v11 interval misses**,
alongside:
1. missing `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=32768` / pre-#43447 image,
2. cross-type system-prompt divergence (monolith vs unit vs page vs metadata),
3. measuring lifetime instead of fleet-window deltas.

### Priority if interval hits stay low after v11

1. Confirm retention env + #43447 image (`26-server-ops-checklist.md`).
2. 10 s `/metrics` deltas during a forced cold canary: interval hit%,
   `local_compute` tokens, prefill p95, `kv_cache_usage`.
3. Only then chase eviction mitigations (lower cross-paper churn, paper
   affinity / fewer distinct long prefixes in flight, future queue-informed
   LRU if #48485 lands).
4. Do **not** re-litigate "turn APC on" — it is already on.

---

## False-pass hypothesis

Treating 96.66% lifetime hit rate as proof that eviction is irrelevant and
that v11 document sharing is already delivering wall wins — then skipping
interval scrapes and shipping "APC done" while cold serial calls still
re-prefill under LRU thrash.

## False-fail hypothesis

Blaming eviction / "need more HBM" for serial re-prefill on a pre-v11 or
non-CLI path that still draws `secrets.token_hex(4)` per call — spending
ops cycles on retention/capacity while hash identity is still broken.

## What would change my mind

A v11 cold canary with retention env verified, HMAC tags confirmed in debug
transcripts, unit/page reorder on, and 10 s metric deltas showing
**interval hit% still &lt;20% on call 2+ of the same paper** while
`kv_cache_usage` is high and free blocks churn — that would promote
**eviction** (or hybrid retention misconfig) above residual client layout
as the primary remaining APC killer.

---

## Sources

- Live pod probe / lifetime metrics: `research/tapetum-llm-speedup/146-verifier-prefix-cache-contradiction.md`
- vLLM APC internals (hash chain, LRU, DSV4 hybrid): `research/tapetum-llm-speedup/92-vllm-apc-internals.md`
- Client HEAD status: `research/cold-run-10min/12-prefix-cache-code-auditor.md`
- Retention / 0%→74.3%: `research/tapetum-llm-speedup/05-web.md` (PR #43447)
- vLLM RFC wait-queue-aware eviction: https://github.com/vllm-project/vllm/issues/48485
- Prefix metrics as token counters: https://github.com/vllm-project/vllm/pull/18003
- Metrics design (interval vs lifetime): https://github.com/vllm-project/vllm/blob/main/docs/design/metrics.md
- DSV4 584 B/token `fp8_ds_mla`: https://github.com/vllm-project/vllm/issues/47648
- MLA ~70 KB/token bf16: Aleph Alpha DeepSeek inference theoretical model (2025-09)
- Distributed cache thrash (multi-replica; secondary here): https://llm-d.ai/blog/kvcache-wins-you-can-see
