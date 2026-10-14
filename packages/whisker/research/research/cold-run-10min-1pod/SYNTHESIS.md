# SYNTHESIS — Cold run ≤10 min on one MoE pod

**Date:** 2026-07-24  
**Constraint:** `alliance-pod` only (DeepSeek-V4-Pro, S=16). Twin V4-Pro **forbidden** (budget/authority).  
**Corpus:** this directory. Prior dual-pod plan in `research/cold-run-10min/` is superseded for execution.

## Verdict

| Path | Central wall | ≤600 s? |
|------|-------------:|:-------:|
| **v11 only** (working tree) | ~1260–1493 s (~21–25 min) | No |
| **MoE-only MODERATE** | ~1366 s (~23 min) | No |
| **MoE-only AGGRESSIVE** (realistic) | ~715–910 s (~12–15 min) | No |
| **Full AGGRESSIVE stack** (`11`) | **~680 s** central (585–910) | No (planning) |
| **Heterogeneous** (MoE + existing dense) + MODERATE cuts | **~511 s** MoE-bound if scoping+parity; **~510–710 s** planning | **Maybe** (design only) |
| Dense pods down / not restarted | Honest SLA **~15–20 min** after MoE package | Impossible at quality |

**≤10 min on one V4-Pro replica alone is below the quality-preserving physics floor** (`17-physics-floor-skeptic.md`: front-end alone 758×20/16 = 948 s). The only arithmetic path under the twin ban is **`wall = max(T_moe, T_dense)`** using an **already-running** dense Alliance endpoint — not a second V4-Pro.

**LIVE BLOCKER (2026-07-24 probe, `26-dense-pod-liveness.md`):** all four dense `SERVICES.toml` endpoints (`h200-qwen3-32b`, `b300-qwen36-27b`, `b200x2-gemma4`, `b200-r1`) return **HTTP 404**. Only `alliance-pod` is up. Heterogeneous Package C is **infra-blocked** until Alliance restarts at least `h200-qwen3-32b`. Policy permission alone is not enough.

## What v11 already buys

Audit: `10-impl-status-1pod.md`. Working-tree `_LANE_VERSION = 11`:

- Metadata short-circuit: **−1059 to −1341 s**
- LJF + `to_thread` + timeouts: **~−60 to −90 s**
- Partial PDF prefix / HMAC; tombstones (warm only)

Expected cold after v11: **~21–25 min**, not the measured 3003 s v10 baseline. Remeasure before claiming further wins.

## Package rollups @ S=16

Full math: `18-packages-1pod.md`.

| Package | Contents | Central |
|---------|----------|--------:|
| CONSERVATIVE | prefix/HMAC/LJF/server APC — no short-circuit | ~2163 s |
| MODERATE | + metadata Tier A+B + verdict-first + residual prefix | ~1366 s |
| AGGRESSIVE realistic | + router + dense offload + optional det-metadata | ~715 s |
| AGGRESSIVE bare optimistic | same, zero friction / unvalidated 2× | ~585 s (hairline) |

## Heterogeneous design (only ≤10 min candidate)

Architecture: `12-dense-offload-architecture.md`. Wall model: `20-heterogeneous-wall.md`.

| Pod | Calls | Role |
|-----|------:|------|
| `alliance-pod` MoE | ~428 | Monolith / HTML tier-1–2 / escalations / oversize units |
| `h200-qwen3-32b` dense | ~1879 | Unit checks + metadata/outline |

At 2× scoped dense decode, wall ≈ **max(~476 s MoE, ~207–511 s dense)** → MoE-bound ~**511 s** if scoping + parity land.

**Hard blockers before ship:**

1. **Payload scoping** (~10–15k/unit) — without it dense collapses to S≤16, L≈20 s → negative EV (`23-payload-scope-dense.md`).
2. **381/381 fused verdict parity** + 16 flip-set equivalence (`19-quality-gate-1pod.md`).
3. Avoid primary: `b200x2-gemma4` (wording false-fail), `b200-r1` (thinking overhead). Reserve: `b300-qwen36-27b` after A/B.

## Remaining MoE-only code levers (ranked)

| # | Lever | Est. @ S=16 post-v11 | Gate |
|---|-------|---------------------:|------|
| 1 | Dense offload | −850 to −1200 s | 381 A/B + scoping |
| 2 | Deterministic metadata | −~471 s | Shadow A/B (`13`) — A/B only |
| 3 | Verdict-first / schema-slim bifurcation | −124 to −155 s | Holdout (`15`, `05n`) |
| 4 | Router combo_safe + dynamic quota | −190 to −310 s | 3/381 + 16/381 (`14`) |
| 5 | Payload scoping | enabler for #1 | Bench dense S |

**Not cold path:** call-class fingerprints (`25`) — 0 s first greenfield; helps prompt-edit reruns only.

**Server ops alone** (`16`): max ~422 s post-SC → still ~25 min. Tier-1 recipe flags yes; never `--max-num-seqs`>16.

## Think-off / DeepSeek / dense class

- Non-think on unit checks only after A/B: `chat_template_kwargs.thinking=false` / `enable_thinking=false` / `reasoning_effort="none"`. Never `reasoning_effort="low"` (maps to High on DSV4). (`05a`, `05c`)
- Re-probe alliance-pod — prior probe may already be Non-think.
- Dense class: **Qwen3-32B** primary; Qwen3.6-27B latency pilot; **not** Gemma-4 (`05f`).
- Flash unit-judge: yes *if deployed* (`05b`); no Alliance Flash endpoint today → out of budget path. Hosted prior: Flash decode only **~1.7×** Pro (not 3.8× active-param theory); think on/off dominates wall (`05z`).
- Cascade lit: escalate ≤15% units to Pro; predictive route, not same-pod MoE→MoE (`05e`, `05l`, `05p`).

## Reject / do-not-bank ledger

| Idea | Verdict | Why |
|------|---------|-----|
| Skip monolith | **No** | Fusion false-clears; 10 min reachable without (`21`) |
| `--det-skip` as default | **No** | Advisory opt-in only; ~250–350 s (`24`) |
| P/D disagg on one 8×H200 | **No** | Short OSL; can't split node (`05k`) |
| `VLLM_BATCH_INVARIANT` | **No** | ~50% throughput hit (`05v`) |
| MTP wall savings | **A/B only** | Short JSON @ c≈16 is lose/flat zone (`05j`) — do not bank |
| Ngram/PLD as MTP substitute | **Marginal** | ~37–75 s; keys only (`05w`) |
| Flash without new deploy | **No** | Needs weights/endpoint (`05b`) |
| Twin / S=32 / c>32 | **Forbidden** | Operator + measured regression |
| `--enable-dbo` at seqs=16 | **Usually flat** | Needs ≥32 concurrent decode tokens (`05t`) |
| Server `guided_grammar` / speculative `guided_json` | **No** | Stay schema-in-prompt (`05i`); guided path is the slow trap |

Server Tier-1: MBT 16384, decode CUDA graphs, EP. Plan **~10–15% tok/s** from `deepep_low_latency` alone at S=16 (`05t`); DBO only if DEP thresholds fire. MTP k=1 / ngram behind acceptance gate. Confirm async-scheduling: if `running≈16` + elevated waiting + soft util under c=32, try `--no-async-scheduling` (`05s`) — never raise S to “fix” underfill. Paper CSA/HCA already on with V4-Pro weights; no hidden 3.7× switch (`05x`).

**Client invariants (CN + hosted):** never `thinking.enabled` with `json_object`; never `thinking.disabled` + `reasoning_effort` (400); do not enable thinking to fix schema (`05y`).

**Shared-pod noise (`28`):** `alliance-pod` is Alliance multi-tenant — HIGH variance risk (~2× wall if half slots stolen; ≥25% flip confound). Measure cold runs off-hours with `/metrics`; never treat single A/B as ground truth without matched occupancy.

## Execution order

1. Remeasure cold fleet on local v11 (truth baseline).
2. Ship MoE package: det-metadata shadow (HTML-first ~251 s staging, then fleet ~471 s — `22`) → verdict-first → router/dynamic quota → server Tier-1 (no MTP banked).
3. **Unblock dense:** ask Alliance ops to restart `h200-qwen3-32b` (all dense 404 today). Until then execute MoE-only path and treat ≤10 min as blocked.
4. After dense is live: payload scoping → cascade (units dense, escalate ≤15%) → ~0.8–1.2 h quality gate (`19`) → enable. If ops will not restart dense: SLA **~15–20 min**.
5. Distill only if Path F (scoped dense + short pass tokens) fails 381 gate (`05g`).

## Out of scope

Second V4-Pro, S=32, c>32, drop verification / skip monolith, SGLang migrate, HTTP micro-tuning, VLM/images, dual-pod LiteLLM shard, BI mode, P/D on one node.

## Index of load-bearing reports

| File | Role |
|------|------|
| `00-baseline.md` | Constraint + measured 3003 s |
| `10-impl-status-1pod.md` | v11 inventory |
| `11-wall-arithmetic-1pod.md` | Slot math |
| `12-dense-offload-architecture.md` | Split + ~511 s |
| `13-deterministic-metadata.md` | A/B-only −471 s |
| `14-router-quota-1pod.md` | Safe −150–250 calls |
| `15-verdict-first-design.md` | −92 to −155 s |
| `16-server-ops-1pod.md` | Ops checklist |
| `17-physics-floor-skeptic.md` | 10 min impossible MoE-only |
| `18-packages-1pod.md` | Package rollups |
| `20-heterogeneous-wall.md` | `max(T_moe,T_dense)` |
| `05*.md` | Web / DeepSeek / eval forage |
