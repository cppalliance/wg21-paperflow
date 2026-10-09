# 51 - Determinism Risk Matrix (speed levers → verdict identity)

**Date:** 2026-07-24  
**Goal:** Map every cold-run speed lever to determinism risk vectors (MoE batch variance, parallel in-paper, MTP, dual-pod) and classify which are **verdict-identity-safe**.  
**Sources:** `research/tapetum-llm-speedup/SYNTHESIS.md`, `47-quality-equivalence.md`, `MODELS.md`, `research/cold-run-10min/*`, `103-vllm-mtp-determinism.md`, `13-in-paper-parallel-risk.md`, `21-dual-pod-sharder.md`, `17-metadata-short-circuit.md`, `26-server-ops-checklist.md`.

---

## Definitions

| Term | Meaning |
|------|---------|
| **Quality-stability** | Same paper in → semantically equivalent trace out (same findings, verdicts, structure). Not bit-exact. Contract in root `CLAUDE.md` and `MODELS.md`. |
| **Verdict-identity-safe** | Lever does not change the four-component equivalence vector on unchanged inputs: `suggested_verdict`, `fusion.combined_verdict`, defect-group multiset (by `defect_type`), coverage tuple (`47-quality-equivalence.md`). Validation: byte-diff sidecars or `flip_AB ≤ flip_AA + margin` on 381-paper fleet. |
| **A/A noise floor** | Identical reruns already flip ≥25% of borderline papers at c=32 (`20-sweep-results.md`, `tapetum_llm.md:31`). Full 381-paper double-A run is mandatory before treating any drift as regression. |
| **Advisory lane** | Tapetum never gates; dissect D11 serial path stays untouched. Variance budget is documented, not zero. |

### Risk vectors (columns)

| Vector | Mechanism | Already active? |
|--------|-----------|-----------------|
| **MoE batch** | DeepSeek-V4-Pro expert routing + non-batch-invariant matmul/attention kernels change logits under batch composition (`MODELS.md:69-70`, `77-78`). |
| **Parallel in-paper** | Concurrent monolith + metadata + units + escalations within one paper increases batch token-shape diversity (`13-in-paper-parallel-risk.md`). |
| **MTP** | Spec-decode verify path runs at batch_size=2; argmax can diverge from plain greedy (`103-vllm-mtp-determinism.md`, vLLM #42518). |
| **Dual-pod** | Same weights, independent schedulers and prefix-cache state; fixed per-paper assignment, but cross-pod A/B differs from single-pod baseline (`21-dual-pod-sharder.md`). |

---

## Master matrix

Legend: **Risk** = determinism impact if lever ships without extra gates. **V-I safe** = verdict-identity-safe on unchanged markdown inputs.

| # | Lever | Package | Wall Δ (est.) | MoE batch | In-paper ∥ | MTP | Dual-pod | Other | Risk | V-I safe? | Gate |
|---|-------|---------|---------------|-----------|------------|-----|----------|-------|------|-----------|------|
| 1 | Metadata-fail short-circuit | MODERATE | ~1341 s | — | — | — | — | Call elimination; strips unit/page calls after metadata cap | LOW verdict / MED inspect | **Yes** (verdict + fusion) | P145 replay; dev-replay recall; `--inspect` bypass |
| 2 | HMAC guard tag + user reorder (v11) | CONSERVATIVE | ~180–1100 s | — | — | — | — | Prompt layout change; APC enabler | MED | **No** | Full 381 A/B + holdout (attention shift on scoped blocks) |
| 3 | Verdict-first / terse pass schema | MODERATE | ~180–360 s | — | — | — | — | Schema + field order change | MED–HIGH | **No** | Full protocol + holdout |
| 4 | Dual-pod shard (same model) | CONSERVATIVE | ~1.9× slots | Indirect | — | — | **Primary** | Second scheduler axis | MED | **Conditional** | 20-PID spot flip check; shard-set fingerprint |
| 5 | Error tombstone fingerprints | CONSERVATIVE | warm 65→10 s | — | — | — | — | Skip path only | NONE | **Yes** | Wall time only when skip fires |
| 6 | LJF paper ordering | CONSERVATIVE | ~30–90 s | — | — | — | — | Scheduling only | NONE | **Yes** | Wall time |
| 7 | `asyncio.to_thread` + token cache | CONSERVATIVE | ~30–40 s | — | — | — | — | CPU prep only | NONE | **Yes** | Wall time |
| 8 | Monolith `wait_for` timeout | CONSERVATIVE | tail only | — | — | — | — | Fails closed on hang | LOW | **Yes** | Error rate only |
| 9 | Server: MBT 16384 | CONSERVATIVE | ~100–250 s | Scheduling | — | — | — | Prefill chunking | NONE | **Yes** | Verdict byte-diff |
| 10 | Server: APC + retention (#43447) | CONSERVATIVE | ~60–180 s | — | — | — | — | Bitwise KV replay | NONE | **Yes** | Prefix hit rate + verdict diff |
| 11 | Server: CUDA graphs FULL_DECODE_ONLY | CONSERVATIVE | ~50–120 s | — | — | — | — | Decode kernel path | NONE | **Yes** | Verdict byte-diff |
| 12 | Server: long-prefill threshold 8192 | CONSERVATIVE | ~30–80 s | Scheduling | — | — | — | Co-tune with MBT | NONE | **Yes** | Verdict byte-diff |
| 13 | Server: chunked prefill (leave on) | — | 0 (default) | Scheduling | — | — | — | Do not disable | NONE | **Yes** | N/A |
| 14 | Server: FP8 KV (already live) | — | 0 incremental | Slight numeric | — | — | — | Already accepted | LOW | **Yes** | Confirm only |
| 15 | **MTP k=1** | MODERATE | ~100–200 s | **Compounds** | — | **Primary** | — | Verify batch_shape=2 | **HIGH** | **No** | Persona-47 A/B; monitor spec_decode acceptance |
| 16 | MTP k=2+ | — | negative on short JSON | **Compounds** | — | **Primary** | — | OSL cliff ~64 tok | HIGH | **No** | Reject for judge lane |
| 17 | **In-paper parallel** (units + wave) | UX / rejected fleet | ~0 s fleet | **Primary** | **Primary** | — | — | W≤12 burst/paper | **HIGH** | **No** | 381 A/B only; `--all-pages` UX experiment |
| 18 | Cross-paper c=32 (live default) | baseline | — | **Primary** | — | — | — | Overfills 16 slots | **HIGH** (baseline) | **No** | Already embedded in flip floor |
| 19 | Raise `--max-num-seqs` to 32 | forbidden | +57% wall | **Primary** | — | — | — | Regressed in measurement | HIGH | **No** | Do not ship |
| 20 | Escalation skip-and-synthesize | MODERATE | ~23 s | — | — | — | — | −18 calls; evidence shape change | LOW–MED | **Conditional** | Dev-replay 9-PID + synthesis rules |
| 21 | Deterministic metadata diff | AGGRESSIVE | ~471 s | — | — | — | — | Replaces LLM call | HIGH | **No** | Full protocol + holdout |
| 22 | Dense-judge offload | AGGRESSIVE | ~850–1200 s (hyp.) | Reduced on offload path | — | — | Optional 2nd pod | **Model swap** | **HIGH** | **No** | 381/381 parity required (persona 23) |
| 23 | Payload scoping (shorter prefill) | AGGRESSIVE | TBD | — | — | — | — | Changes LLM inputs | HIGH | **No** | Full protocol |
| 24 | Per-unit fingerprint skip | warm/rerun | rerun only | — | — | — | — | Changes call multiset | LOW on warm | **Conditional** | Greenfield cold: 0 calls saved |
| 25 | HTTP client pooling | rejected | ~5–17 s | — | — | — | — | Transport only | NONE | **Yes** | Not worth pipeline change |
| 26 | Multi-unit prompt packing | rejected | — | **Primary** | — | — | — | Rubric degradation | HIGH | **No** | Rejected (RuVerBench) |
| 27 | `VLLM_BATCH_INVARIANT=1` | infra | −MTP gain | **Mitigates** | Mitigates | Mitigates | Mitigates | ~50% throughput cost | LOW if enabled | **Yes** (bit-stable) | Pod benchmark; V4-Pro not on tested list |

---

## Risk vector deep dives

### MoE batch variance

**Active today** at production settings: client c=32, server `--max-num-seqs 16`, serial in-paper calls. Batch non-invariance is not introduced only at higher concurrency; it is already in the baseline flip floor (`16-determinism-auditor` persona, `13-in-paper-parallel-risk.md:65-69`).

| Lever | Effect on MoE variance |
|-------|------------------------|
| Raises concurrent heterogeneous prompts | **Worsens** — in-paper parallel, c>32, slots=32 |
| Changes batch neighbors only | **Worsens incrementally** — dual-pod (fixed per paper after assign) |
| Same token stream, scheduling-only | **Neutral** — MBT, APC, LJF, tombstones |
| Removes calls without changing survivors | **Neutral** — metadata short-circuit |
| Changes decode kernel path | **Uncertain** — MTP compounds existing variance |

### Parallel in-paper

Mechanically dependency-safe (`13-in-paper-parallel-risk.md:41-43`) but **not verdict-identity-safe**: W≤12 parallel wave co-schedules monolith prefill + page escalation + unit checks with full `candidate_md`, increasing batch token-shape diversity with **~0 s fleet wall savings** (slot accounting unchanged).

Ship: **A/B only**, never default-on for fleet.

### MTP

Greedy rejection sampling is algorithmically lossless but **not hardware bit-exact** (`103-vllm-mtp-determinism.md`):

- Verify forward at batch_size=2 vs decode at batch_size=1 → ULP deltas → argmax flip (#42518).
- CUDA graphs on H200 may mask eager-mode divergence; MoE + continuous batching caveat remains.
- `VLLM_BATCH_INVARIANT=1` fixes token parity but erases most MTP throughput (~3× slowdown in repro).

Classification: **MODERATE package, A/B-gated**, not CONSERVATIVE.

### Dual-pod

Same model + weights; deterministic `sorted(pids)[index % len(live_pods)]` assignment (`21-dual-pod-sharder.md:10-14`).

- Per-paper pod **fixed across reruns** → incremental skip stable.
- Versus historical all-`alliance-pod` baseline, some papers may differ on first adoption (second variance axis).
- Does **not** violate advisory-only contract; exceeds production bit-identical bar same as today.

Classification: **verdict-identity-safe conditional** — 20-PID spot check recommended; not exempt from flip-floor math on first fleet adoption.

---

## Verdict-identity-safe levers (summary)

These levers change **scheduling, caching, sharding, or skip logic** without changing LLM inputs on calls that still run. Gate: **381-paper verdict byte-diff** (or reuse weekly A/A baseline + margin), not full semantic revalidation.

| Safe (ship with byte-diff gate) | Notes |
|--------------------------------|-------|
| Metadata-fail short-circuit | 0/32 verdict changes when units stripped (P145); defect groups may drop on inspect path |
| Error tombstone fingerprints | Skip unchanged errors; same cascade when evaluated |
| LJF ordering | Same call multiset |
| `to_thread` + candidate token cache | CPU-only |
| Monolith `wait_for` | Same prompts unless timeout fires |
| Server MBT 16384 | Scheduling |
| Server APC + retention | Bitwise KV prefix replay |
| Server CUDA graphs FULL_DECODE_ONLY | Decode path |
| Server long-prefill threshold 8192 | Scheduling |
| Chunked prefill (keep on) | Default |
| FP8 KV | Already live |
| HTTP pooling | Transport (negligible savings) |
| `VLLM_BATCH_INVARIANT=1` | Infra ask; restores bit-stability at throughput cost |

| Conditional (spot-check or narrow gate) | Notes |
|-------------------------------------------|-------|
| Dual-pod shard | Same prompts; 20-PID flip spot + shard-set fingerprint |
| Escalation dedupe | 18 calls; synthesis must preserve grounded omissions |
| Per-unit fingerprint | Warm/rerun only; changes which calls fire |

---

## Not verdict-identity-safe (full protocol required)

Full gate: 381-paper A/B vs A/A floor + dev-replay recall (9 PIDs) + holdout (48 anchors) when evidence-touching.

| Lever | Primary risk |
|-------|--------------|
| HMAC + user reorder | Prompt attention shift despite security-equivalent tag |
| Verdict-first / terse schema | Schema corridor + reasoning field changes |
| **MTP k=1+** | Verify-path batch shape + structured JSON edge cases |
| **In-paper parallel** | MoE burst composition |
| Cross-paper c>32 / slots=32 | Forbidden; worsens MoE |
| Dense-judge offload | Model family change |
| Deterministic metadata diff | Replaces LLM judgment |
| Payload scoping | Truncated evidence |
| Multi-unit packing | Rubric degradation |

---

## Recommended bundle order (determinism-first)

Aligns with `SYNTHESIS.md` §5, optimized to stack **V-I safe** levers before A/B-tax levers:

1. **Server flags (V-I safe):** MBT, APC+retention, CUDA graphs, long-prefill — one restart, one byte-diff run.
2. **Client scheduling (V-I safe):** tombstones, LJF, remaining `to_thread`/cache — no lane bump for scheduling-only items.
3. **Call elimination (V-I safe on verdict):** metadata short-circuit — lane bump; dev-replay recall check.
4. **Dual-pod (conditional):** health probe both pods; shard-set fingerprint; 20-PID spot.
5. **Prompt layout (not V-I safe):** HMAC/reorder already v11 — treat as settled only after holdout A/B archived.
6. **MTP (not V-I safe):** last MODERATE item; disable first on verdict diff regression.
7. **Never fleet-default:** in-paper parallel, slots=32, dense-judge without parity proof.

---

## False-pass / false-fail (matrix-level)

**False-pass:** Ship MTP + in-paper parallel together; wall drops but `flip_AB` exceeds `flip_AA + margin` on borderline table/structure papers; operator treats faster run as quality-equivalent because advisory lane already tolerates ≥25% churn.

**False-fail:** Reject dual-pod or metadata short-circuit because single-pod wall stays >600 s — conflating infra multiplier with call elimination; both are V-I safe on verdict algebra.

---

## What would change this matrix

1. Full **381-paper double-A** showing `flip_AA < 5%` on the four-component vector → tighten margin; contradicts current MoE docs unless `VLLM_BATCH_INVARIANT` deployed.
2. Persona-47 MTP A/B: **0 pass/review/fail/error delta** on 381 papers → promote MTP to V-I safe (CONSERVATIVE).
3. In-paper parallel A/B: fleet wall within ±2% **and** flip rate within MoE drift band → promote to conditional for `--all-pages` only.
