# Prior corpus distill — what 1-pod planning keeps

**Date:** 2026-07-24  
**Constraint:** twin V4-Pro forbidden (`ADR-001`). `S_eff = 16` on `alliance-pod` only.  
**Audience:** downstream planner. Prefer this file over re-reading full prior trees.

Related: `DELTA-FROM-DUALPOD.md`, `ADR-001-no-twin-pod.md`, `../27-dualpod-dependency-rewrite.md`.

---

## Corpus map (brief)

| Corpus | Role | Size / shape |
|--------|------|----------------|
| `research/tapetum-llm-throughput/` | Why wall jumped 692→~2886 s; call census | 19 files: `00-baseline`, `01`–`14` auditors, `05-web`, `SYNTHESIS`, `_index`, `opus-A-verification` |
| `research/tapetum-llm-speedup/` | 48 min → 5–10 min program; lever packages | Jul-23 swarm (~150 agents); `SYNTHESIS.md` is the package table |
| `research/cold-run-10min/` | Fresh dual-pod path to ≤10 min | Jul-24; Path A = MODERATE + twin → ~596 s central |

`tapetum-llm-throughput/*` listing (names only):  
`00-baseline.md`, `01-call-count-accountant.md`, `02-prompt-token-auditor.md`, `03-cascade-topology-auditor.md`, `04-concurrency-plumbing-auditor.md`, `05-server-slot-analyst.md`, `05-web.md`, `06-regression-bisector.md`, `07-retry-timeout-auditor.md`, `08-fingerprint-incremental-auditor.md`, `09-escalation-cost-auditor.md`, `10-evidence-verification-cost.md`, `11-output-token-decode-auditor.md`, `12-false-economy-hunter.md`, `13-determinism-guardian.md`, `14-steelman.md`, `SYNTHESIS.md`, `_index.md`, `opus-A-verification.md`.

---

## 1. `tapetum-llm-throughput` — KEEP

Diagnosis of the regression. Still load-bearing for 1-pod planning.

| Keep | Why |
|------|-----|
| Wall ≈ `calls × L / 16` identity | Ceiling is slots × call volume, not "lost client concurrency" |
| Source-aware lane ≈6 calls/paper (2284 / 381) | Explains 4.2× wall vs old ~1 call/paper benchmark |
| Client c=32 over 16 server slots is correct plumbing | Do not re-open c>32 or blame the gather/semaphore path |
| Fusion-dead / routing waste framing | Metadata fail caps before units; many units return zero defects |
| No-source-packet unit slot waste | Client fix still valid on one pod |
| Error tombstones after full cascade | Warm/retry granularity; fingerprints already in later corpora |
| Reject ledger: c>32, slots 16→32, multi-unit packing as free wins | Confirmed again in cold-run-10min; ADR-002 inherits slots ban |
| Docling/olmocr/etc. are different workload class | Extraction + small dense; no MoE judge — do not copy their "speed" |

## 1b. `tapetum-llm-throughput` — IGNORE / DOWNRANK

| Ignore | Why |
|--------|-----|
| Dual-pod as optional ~2× lever "allowed-with-conditions" | Twin ban; replace with dense hetero offload, not a second V4-Pro |
| Any plan that treats dual-pod as the primary 10 min closer | Superseded by `ADR-001` |
| Lifetime APC hit-rate as sole evidence of prefix health | Later corpora require fleet-window `/metrics` + sidecar timings |
| Prompt/schema growth as regression driver | Already ruled noise (~single-digit %) |

---

## 2. `tapetum-llm-speedup` — KEEP

Root findings and quality bar. Package **names** stay; package **walls that assume dual-pod** do not.

| Keep | Why |
|------|-----|
| Ranked waste: 44.6% fusion-dead units after metadata fail/review | Still the largest N cut (~1341 s @ S=16 / Tier C framing; Tier A+B ~1059 s) |
| HMAC per-paper guard + document-first reorder | Prefix/APC enablement; security-equivalent vs random tag |
| Decode waste on pass path (~55 tok reasoning unused) | Feeds verdict-first / terse pass schema |
| Client stalls: LJF, `to_thread(screen_pages)`, monolith `wait_for` | Already largely landed; keep in CONSERVATIVE |
| Tombstone fingerprints → warm 65 s → ~10–15 s | Cold target ≠ warm steady state (steelman) |
| Quality gate protocol (A/A floor once; A/B per prompt/schema lever; verdict-identity for schedule/cache) | Non-negotiable; 1-pod dense offload needs the stronger parity gate |
| Reject: SGLang migration, HTTP retune, multi-unit packing, cross-paper memo as cold levers | Still noise/reject |
| Long-term dense judge distillation (~1510 labels/run) | Separate program; directionally correct for "docling-class" speed |
| Non-finding: APC is ON (not off) | Do not reopen "turn on prefix cache" as if server APC were disabled |

## 2b. `tapetum-llm-speedup` — IGNORE / SUPERSEDED numerically

| Ignore or rewrite | Why |
|-------------------|-----|
| CONSERVATIVE **~685–856 s** and MODERATE **~596 s (530–670)** as ship targets | Those walls **include dual-pod shard** in the package definition |
| "Dual-pod sharding … ~1.9× on remaining wall" as an executable Day-N step | Forbidden; see `DELTA-FROM-DUALPOD.md` |
| Execution order step 4 = dual-pod before AGGRESSIVE | Reorder: finish MoE software, then dense offload (or honest SLA) |
| Implied "one H200" hardware story | Alliance-pod is already 8×H200 TP8+EP; wider EP ≠ second replica (`cold-run-10min/53`) |

**Keep the lever list; drop the dual-pod term from every stacked wall.**

---

## 3. `cold-run-10min` — KEEP (software / ops / measurement)

Jul-24 corpus updated impl status and external ops. Most client levers still apply at S=16.

| Keep | Why |
|------|-----|
| Baseline anchors: 2883–3003 s cold, ~2284 calls, L≈20 s, S=16 | Arithmetic identity unchanged |
| v11 short-circuit (fail **and** review) already in working tree | Day 0 = measure post-v11 single-pod truth (~20–25 min expected) |
| Impl gaps still open: text-lane HMAC, escalation dedupe, verdict-first, per-call timings, dual-pod CLI | Dual-pod CLI → **drop**; others remain |
| Overlap-correct stacking (`11-wall-arithmetic.md`) | N cuts first; rescale L_abs to survivors; do not double-count |
| Single-pod MODERATE ceiling **~1490–1493 s** | Honest MoE-only floor after twin ban |
| Forbidden: `--max-num-seqs` 16→32 (+57% wall) | ADR-002 |
| Ops checklist: `deepseek_v4` parsers, MBT 16384, APC on, DeepEP/DBO A/B, MTP k=1 gated | Server levers still valid on one pod |
| Reject: SGLang, HTTP client retune, NVFP4/Blackwell for this goal, Docling "speed" analogies | Unchanged |
| Quality caveats: review short-circuit drops inspect sub-findings; need `--inspect` / exhaustive when reports matter | Unchanged |
| Dense-judge offload as Path B option 2 | **Promoted** to primary ≤10 min candidate under twin ban |
| Steelman: warm already ~65 s; 10 min is for lane-bump cold | Unchanged |

## 3b. `cold-run-10min` — SUPERSEDED (dual-pod Path A)

Treat the following as **historical / blocked context only**. Cite as superseded, never as the ship path.

| Superseded claim | Replacement under twin ban |
|------------------|----------------------------|
| "≤10 min yes with MODERATE + dual-pod (~596 s central)" | MoE-only MODERATE misses; need AGGRESSIVE + dense hetero or honest ~15–25 min SLA |
| Path A Day 3: revive twin + `--shard-pods` | Do not revive; no second V4-Pro in plan |
| Dual-pod Semaphore(16)×2 → ÷~1.9 / **−887 s** on MODERATE remainder | Capacity must come from call cuts + L cuts + `max(T_moe, T_dense)` |
| Decision line: "revive twin **or** accept ~20–25 min" | Twin option closed; accept MoE SLA **or** dense Package C |
| Dual-pod shard algorithm cards as critical-path eng (`67`, `45`, LiteLLM reject for MoE fan-out) | Reuse patterns only for **call-class / dense** routing, not PID%2 MoE split |
| Cross-pod MoE verdict-drift gate as the dual-lane quality check | Dense vs MoE teacher parity (381/381) instead |
| "Second live DeepSeek endpoint" as option 1 for Path B | Forbidden (budget/authority); dense endpoint ≠ DeepSeek replica |
| Hardware uplift "8×H200" as if alliance were 1×GPU | Already 8×; not a substitute for −887 s |

**Still useful as evidence of the gap:** `11-wall-arithmetic.md` dual vs single tables, `22-path-a-b-10min.md`, `15-dual-pod-liveness.md` (404 twin), `53-multi-gpu-ep.md` (−887 s vs EP widening).

---

## 4. Quick planner checklist

1. **Reuse** call census, overlap stacking, quality gates, reject ledger (slots/c/SGLang/HTTP).
2. **Ship** remaining MoE software: measure v11, finish HMAC text lane, escalation dedupe, timings, verdict-first A/B.
3. **Do not schedule** twin revive, `--shard-pods` MoE, S=32, or dual-pod walls (~596 s).
4. **For ≤600 s:** plan dense hetero offload + AGGRESSIVE N cuts (`../12-dense-offload-architecture.md`, `../18-packages-1pod.md`), or publish a higher SLA.
5. **Numbers:** see `DELTA-FROM-DUALPOD.md` for the explicit −887 s / ~1493 vs ~596 comparison.
