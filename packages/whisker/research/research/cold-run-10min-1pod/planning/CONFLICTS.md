# CONFLICTS — Contradictory claims across corpora

**Date:** 2026-07-24  
**Resolved position** = what planners must assume unless new measurements overturn it.  
**Canonical arbiter:** `research/cold-run-10min-1pod/SYNTHESIS.md` + cited 1-pod report IDs.

---

## Conflict index

| # | Topic | Competing claims | Resolved position |
|---|-------|------------------|-------------------|
| 1 | MTP | “Yes / modest win in MODERATE” vs “A/B; short JSON lose zone” | **A/B only; do not bank wall seconds** |
| 2 | Dense ~511 vs ~680 | Two “central” walls | **Different architectures** — both valid in-scope |
| 3 | Flash 3.8× vs ~1.7× | Active-param theory vs hosted decode | **Plan L with ~1.7×; think mode >> tier** |
| 4 | Path to ≤10 min | Twin dual-pod vs heterogeneous dense | **Twin forbidden; dense cascade only design path** |
| 5 | Hardware shape | “1×H200” vs “already 8×H200” | **One replica on 8×H200 TP8+EP; S_eff still 16** |
| 6 | Dense pod liveness | Inventory “live” vs probe 404 | **All dense 404 today; Package C blocked** |
| 7 | MTP short-JSON amortize | cold-run `05d` vs 1-pod `05j` | **Prefer `05j` for fleet short JSON @ c≈16** |
| 8 | DBO at seqs=16 | Ops “enable” vs flat | **Usually flat; DeepEP first** |
| 9 | Shared-pod / flip noise | Single A/B as truth vs HIGH confound | **Off-hours + matched occupancy; never one-shot** |
| 10 | External “speed” | Docling 3.8 p/s vs our 48 min | **Different workload class; ignore as MoE prior** |

---

## 1. MTP: bankable win vs A/B-only

### Claims

| Source | Claim |
|--------|-------|
| `tapetum-llm-speedup/SYNTHESIS.md` MODERATE package | MTP spec-decode **A/B-gated** inside path to ~596 s dual-pod stack |
| `cold-run-10min/05d-web-mtp-specdecode.md` | MTP k=1 is a **real decode lever**; short judge JSON (~55–200 tok) “usually OK” if decode-bound; modest wall (~7–16%), not solo 10 min |
| `cold-run-10min/SYNTHESIS.md` | MTP k=1 possible modest win; can **hurt** at high concurrency / short OSL; A/B required |
| `cold-run-10min-1pod/05j-web-mtp-short-json.md` | Short structured JSON @ concurrency ~16: **hurt or flat** prior; GB300 OSL=64 cliff; QPS collapse by ~8; **do not bank** |
| `cold-run-10min-1pod/SYNTHESIS.md` reject ledger | MTP wall savings → **A/B only** |

### Why they diverge

`05d` optimizes for “decode-bound unit check with tens–hundreds of tokens.” `05j` fixes the *fleet* regime: server S=16, client c=32, verdict-first/short JSON, long ISL prefill. Same flag, different amortization math. Speedup MODERATE never said “bank MTP”; later readers treated A/B-gated as “in the central stack.”

### Resolved position

1. **Do not put MTP seconds in central ≤600 s arithmetic.**  
2. Optional ops probe: `method=mtp`, **k=1 only**, CUDA-graph decode, log acceptance + JSON validity + wall.  
3. Keep if acceptance ≥~70%, no JSON regression, material wall win; else leave **off**.  
4. Prefer **off** if forced binary before A/B on short-JSON-dominant traffic.  
5. Ngram/PLD substitute: marginal (~37–75 s), keys only (`05w`) — also not banked.

---

## 2. Dense ~511 s vs AGGRESSIVE ~680 s

### Claims

| Figure | Meaning | Source |
|------|---------|--------|
| **~680 s** (585–910) | Full **MoE-only** AGGRESSIVE stack central (single queue, S=16) | `11-wall-arithmetic-1pod.md`, `SYNTHESIS` “Full AGGRESSIVE stack” |
| **~715 s** | AGGRESSIVE **realistic** (friction) MoE path | `18`, `SYNTHESIS` package table |
| **~585 s** | AGGRESSIVE bare optimistic (zero friction / unvalidated 2×) | Same — **not** shippable target |
| **~511 s** | Heterogeneous **`max(T_moe, T_dense)`** MoE-bound after scoping + 2× dense decode | `12`, `20`, `SYNTHESIS` |
| **~510–710 s** | Heterogeneous planning band | `12` |

### Resolved position

These are **not** rival estimates of the same system:

```
MoE-only wall     ≈ (N_rem × L_eff) / 16 + …
Heterogeneous wall ≈ max(T_moe, T_dense) + T_client
```

| If planner means… | Use |
|-------------------|-----|
| Ship without dense restart | ~12–15 min honest; **~680–715 s** central AGGRESSIVE MoE — **misses 10 min** |
| Design after dense alive + scoping + parity | **~511 s** MoE-bound *candidate* — only ≤600 s path under twin ban |
| Dense stays 404 | SLA **~15–20 min**; ≤10 min impossible at quality |

Do not average 511 and 680. Do not cite 511 as “MoE-only AGGRESSIVE.”

---

## 3. Flash: 3.8× vs ~1.7×

### Claims

| Source | Claim |
|--------|-------|
| `05b-web-flash-vs-pro.md` | Active params 49B / 13B ≈ **3.8×** less activate → decode *advantage* framing |
| Hosted blogs / AA (via `05z`) | Flash decode **~1.5–1.8×** Pro (central **~1.7×**) same think mode |
| `05z` CRITICAL | **Think on/off dominates** wall (~8–9× E2E), not Flash vs Pro decode |
| Naive plans | Scale wall by 49/13 or treat Flash as free 4× on alliance-pod |

### Resolved position

1. **Planning prior for decode-bound L:** Flash ≈ Pro / **1.7** at fixed think mode.  
2. **Do not** scale by active-param **3.8×**. MoE serving compresses the gap.  
3. Flash unit-judge is **yes if deployed** + A/B; **no Alliance Flash endpoint today** → out of budget path (`05b`). Swapping `alliance-pod` to Flash loses Pro on that node.  
4. Think budget (Non-think / high / max) moves `L_eff` more than model tier; probe Non-think kwargs before chasing Flash deploy.  
5. Docling’s **3.8 pages/s** is a *different* 3.8 (258M VLM extraction) — never conflate with Flash param ratio.

---

## 4. Dual-pod ~596 s vs twin forbidden

### Claims

| Source | Claim |
|--------|-------|
| `tapetum-llm-speedup` MODERATE | ~596 s central with dual-pod + short-circuit + … |
| `cold-run-10min/SYNTHESIS` Path A | Revive twin; ~530–670 s; recommended |
| Operator / 1-pod baseline | Twin V4-Pro / `h200x8-deepseek-v4-pro` **forbidden** (budget/authority) |
| Twin probe | Twin also **404** today |

### Resolved position

- Dual-pod arithmetic remains a **correct counterfactual** if a second Pro replica existed.  
- **Execution plans must not** schedule twin revive, LiteLLM dual shard, or CONSERVATIVE packages that embed dual-pod.  
- Replacement ≤10 min design: **heterogeneous dense cascade** (Option B), not a second Pro.  
- If dense cannot restart and twin stays banned: **Option C** — publish ~15–20 min SLA.

---

## 5. Hardware: 1×H200 vs 8×H200

### Claims

| Source | Claim |
|--------|-------|
| `tapetum-llm-speedup/SYNTHESIS.md` header | “Pod: DeepSeek-V4-Pro (MoE) on **1×H200**” |
| `cold-run-10min/SYNTHESIS` + recipe cards | Alliance already **8×H200 TP8+EP**; official recipes mean full node |
| Implicit hope | Wider EP / “more GPUs on the node” alone hits 10 min |

### Resolved position

- Serving shape is **one V4-Pro replica** on a multi-GPU node (TP8+EP class), not a literal single GPU.  
- **S_eff remains 16** (recipe-aligned). Extra GPUs on the *same* replica do not multiply slots the way a second replica would.  
- Hitting 10 min still needs **N cuts + L cuts** and/or **parallel capacity** (dense offload or a second *replica*, the latter forbidden).

---

## 6. Dense pods “live” vs all 404

### Claims

| Source | Claim |
|--------|-------|
| `cold-run-10min/16-dense-judge-candidates.md` (inventory) | Four dense services as live open-weight pods from `SERVICES.toml` |
| Throughput personas (`105`, etc.) | Wall models assuming dense S=32–48 and L≈10 s |
| `26-dense-pod-liveness.md` (2026-07-24 probe) | **0/4** return 200 on `/v1/models`; all **404**; only `alliance-pod` up |

### Resolved position

- Treat dense offload wall (~511 s band) as **design-only until probe green**.  
- Minimum unblock: restart **`h200-qwen3-32b`**.  
- Never schedule Package C / Option B without a same-day health probe.  
- Inventory ≠ liveness.

---

## 7. Short-JSON MTP: `05d` vs `05j` (detail)

| Axis | `cold-run-10min/05d` | `cold-run-10min-1pod/05j` |
|------|----------------------|---------------------------|
| OSL | 55–200 tok “usually above” GB300 cliff | Pass-path / terse JSON nearer **cannot amortize** |
| Concurrency | Modest win at medium QPS | **c≈16 saturated** → ~1.0× from PR #12755 tables |
| Plan use | Optional decode lever | **Hurt/flat prior; A/B; prefer off** |

**Resolved:** For 1-pod fleet planning, **`05j` wins**. Keep `05d` for enablement mechanics and bug watchlist (JSON×reasoning×MTP patches, missing MTP head on quants).

---

## 8. `--enable-dbo` at seqs=16

### Claims

| Source | Claim |
|--------|-------|
| Earlier ops notes (`cold-run-10min` DeepEP+DBO “actionable A/B”) | Bundle both flags |
| `05t-web-dbo-deepep.md` / 1-pod SYNTHESIS | DBO **usually flat** at seqs=16; needs ≥32 concurrent decode tokens; plan **~10–15% tok/s** from `deepep_low_latency` alone |

### Resolved position

- Tier-1: DeepEP low-latency **yes** (expect modest tok/s).  
- DBO: only if DEP thresholds fire under load — **not** a banked second cut.  
- Never raise S to 32 to “make DBO/MTP work.”

---

## 9. Measurement: single A/B vs shared-pod noise

### Claims

| Source | Claim |
|--------|-------|
| Informal practice | One cold A/B settles a lever |
| `28-shared-pod-noise.md` | Multi-tenant alliance-pod: ~2× wall if half slots stolen; ≥25% flip confound |
| Quality protocols (`19`, speedup §4) | Need A/A floor + matched conditions |

### Resolved position

- Cold A/B **off-hours** with `/metrics` occupancy match.  
- Never treat a single wall delta as ground truth without occupancy context.  
- Flip gates use fleet A/A noise floor, not exact-match 0%.

---

## 10. External extractors “faster”

### Claims

| Source | Claim |
|--------|-------|
| Ecosystem marketing / early personas | Docling / olmocr / MinerU prove we are “slow” |
| `tapetum-llm-speedup/SYNTHESIS` §1 | They do **extraction** with small dense models and **no** production MoE judge |

### Resolved position

Different workload. Portable ideas (prefix layout, distill later) stay; their page/s numbers **do not** enter tapetum wall models.

---

## Secondary tensions (quick resolve)

| Tension | Resolve |
|---------|---------|
| cold-run Path B “dense *or* twin *or* hardware uplift” vs 1-pod | Twin out; hardware uplift ≠ second replica; dense is the remaining ≤10 min design |
| Skip monolith for speed (`21` revisit) vs keep | **Keep monolith**; 10 min reachable without skip; fusion false-clear risk |
| `VLLM_BATCH_INVARIANT` for determinism vs throughput | **No** for cold-wall program (~50% hit) |
| Flash better than Pro on rule-literal JSON (CN forums `05y`) vs Pro for hard agentic | Trial Flash/dense on **unit** checks; keep Pro for monolith/escalation; escalate ≤15% |
| Gemma-4 as dense candidate vs reject | **Not primary** (wording false-fail); Qwen3-32B primary |
| Ideal-verify deletion as 10 min lever | ~60–90 s only — not a program |
| Async scheduling underfill → raise S | Try `--no-async-scheduling` if metrics show waiting+soft util; **never** raise S (`05s`) |

---

## Planner checklist (copy into plan preamble)

- [ ] Central wall uses **MoE-only ~680–715 s** or **heterogeneous ~511 s**, never a blend  
- [ ] **No MTP / Flash 3.8× / DBO** seconds in the committed stack  
- [ ] Twin dual-pod **absent** from tickets  
- [ ] Dense work gated on **live probe** of `h200-qwen3-32b`  
- [ ] S=16 and c≤32 stated as invariants  
- [ ] Measurement protocol cites shared-pod noise (`28`)  
- [ ] Contradictions deferred to this file + `CROSS-CORPUS-INDEX.md`

---

## Sources (load-bearing)

- `../SYNTHESIS.md`, `../PLANNING-HANDOFF.md`  
- `../11-wall-arithmetic-1pod.md`, `../12-dense-offload-architecture.md`, `../18-packages-1pod.md`, `../20-heterogeneous-wall.md`  
- `../05b-web-flash-vs-pro.md`, `../05j-web-mtp-short-json.md`, `../05z-web-hosted-latency.md`, `../05t-web-dbo-deepep.md`, `../26-dense-pod-liveness.md`, `../28-shared-pod-noise.md`  
- `research/cold-run-10min/{SYNTHESIS.md,05d-web-mtp-specdecode.md}`  
- `research/tapetum-llm-speedup/SYNTHESIS.md`  
- `research/slots-32-regression/SYNTHESIS.md`  
- `packages/whisker/research/deepseek-v4-pro/SYNTHESIS.md`
