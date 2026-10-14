# PLANNING HANDOFF — Cold-run ≤10 min (1 MoE pod)

**Audience:** a downstream planning agent (any LLM) that must produce an architecture/execution plan.  
**Date:** 2026-07-24  
**Constraint (hard):** no second DeepSeek-V4-Pro pod (budget/authority). `S_eff=16` on `alliance-pod` forever.  
**Canonical synthesis:** [`SYNTHESIS.md`](SYNTHESIS.md)  
**This file:** single entry point. Read this first, then open cited cards. Do not re-forage the dual-pod plan as executable.

---

## 1. Problem statement

Cut `whisker-tapetum-llm` **bare full-fleet cold** (381 papers) from measured **~2883–3003 s (~48–50 min)** to **≤600 s (~10 min)** under quality-stability (fused verdict parity).

This is **not** dissect, **not** `--all-pages` golden review. Call census ~2284 LLM calls (~6/paper) on DeepSeek-V4-Pro via `alliance-pod`.

Warm incremental after fingerprints: ~64.8 s (irrelevant to cold after `_LANE_VERSION` bump).

## 2. Hard constraints (non-negotiable)

| ID | Constraint | Evidence |
|----|------------|----------|
| C1 | Twin V4-Pro / `h200x8-deepseek-v4-pro` **forbidden** | operator 2026-07-24 |
| C2 | `--max-num-seqs` stays **16** on MoE | slots=32 measured **+57%** wall |
| C3 | Client `c>32` forbidden | RunPod 524 / regression corpus |
| C4 | Quality-stability: same fused verdicts/structure | CLAUDE.md / MODELS.md |
| C5 | No skip monolith as default | `21-skip-monolith-revisit.md` |
| C6 | Images/VLM out of scope | operator |
| C7 | Dense offload only if **live** Alliance dense pods | `26` — all dense **404 today** |

## 3. Physics verdict (must not be rediscovered)

```
wall ≈ (N_rem × L_eff) / 16 + T + C − L_abs     # single MoE queue
wall ≈ max(T_moe, T_dense) + T_client           # heterogeneous
```

| Floor | Wall | Note |
|-------|-----:|------|
| Front-end only (381+377) | **948 s** | Already >600 s before units |
| Quality MODERATE survivors (N≈1419) | **~1366–1493 s** | ~23–25 min |
| MoE-only AGGRESSIVE realistic | **~680–715 s** | Still misses 10 min |
| Heterogeneous + scoping + parity | **~511 s** MoE-bound | Only ≤600 candidate |
| Dense pods all 404 | **blocked** | Package C infra-dead |

**MoE-only cannot hit 10 min at quality.** Honest SLA without dense restart: **~15–20 min**.

## 4. Architecture options for the planner

### Option A — MoE-only (shippable without infra)

**Goal:** ~12–23 min cold (honest).  
**Levers:** v11 short-circuit (landed) → det-metadata → verdict-first → router/quota → server Tier-1.  
**Do not promise ≤10 min.**

### Option B — Heterogeneous cascade (only ≤10 min design)

```
T0 CPU:     det metadata / short-circuit
T1 dense:   unit checks (+ optional metadata LLM) on h200-qwen3-32b
T2 MoE:     monolith, HTML tier-1/2, oversize, escalate ≤15%
```

**Prereqs:** (1) Alliance restarts `h200-qwen3-32b`, (2) payload scoping ~10–15k, (3) 381/381 parity gate ~0.8–1.2 h.  
**Wall model:** `max(T_moe≈476s, T_dense≈207–511s) ≈ 511s` if 2× dense decode holds.

### Option C — Reset SLA

If dense will not be restarted and twin stays forbidden: publish **~15–20 min** as the goal; stop the 10-min program.

## 5. Decision checklist (planner must answer)

1. **SLA:** keep ≤10 min (requires dense restart) or reset to ~15–20 min?
2. **Dense restart:** ask Alliance to bring up `h200-qwen3-32b` (yes/no/when)?
3. **Ship v11** working-tree short-circuit as committed baseline (yes)?
4. **Det-metadata:** HTML-first staging then fleet (A/B gate) — schedule?
5. **Verdict-first schema bifurcation** — schedule after det-metadata?
6. **Router combo_safe + dynamic MAX_UNIT_CHECKS** — holdout on 3/381 + 16/381?
7. **Server ops:** MBT 16384, CUDA graphs, DeepEP low-latency (~10–15%); MTP k=1 A/B only (do not bank)?
8. **Non-think probe** on alliance-pod for unit checks (confirm kwargs)?
9. **Reject permanently:** twin, S=32, skip monolith, BI mode, P/D, guided_grammar, default det-skip?
10. **Measurement protocol:** off-hours + `/metrics` matched occupancy (`28` HIGH shared-pod noise)?

## 6. Recommended execution phases (planner may reorder)

| Phase | Work | Unlocks |
|-------|------|---------|
| P0 | Remeasure cold on local v11 | Truth baseline (~21–25 min expected) |
| P1 | Commit/ship v11 levers already in tree | Stable short-circuit |
| P2 | Det-metadata shadow A/B (HTML-first → fleet) | −~251 then −~471 s |
| P3 | Verdict-first + router/quota | −~200–450 s stack |
| P4 | Server Tier-1 flags (ops) | L cut; not enough alone |
| P5 | **Alliance:** restart dense pod | Unblocks Option B |
| P6 | Payload scoping + call-class router | Dense S=32–48 |
| P7 | Cascade + quality gate (`19`) | Ship Option B or fail closed |
| P8 | Distill only if P7 quality fails | Parallel program |

## 7. Live infra status (2026-07-24)

| Endpoint | Status |
|----------|--------|
| `alliance-pod` (DeepSeek-V4-Pro) | **UP** (200) |
| `h200x8-deepseek-v4-pro` twin | **404** (dead; forbidden anyway) |
| `h200-qwen3-32b` | **404** |
| `b300-qwen36-27b` | **404** |
| `b200x2-gemma4` | **404** |
| `b200-r1` | **404** |

## 8. Reject ledger (do not re-open without new evidence)

Twin pod · S=32 · c>32 · skip monolith · default `--det-skip` · P/D on one 8×H200 · `VLLM_BATCH_INVARIANT` · bank MTP seconds · Flash without deploy · Gemma-4 as primary unit judge · server guided_grammar · same-pod MoE→MoE cascade · ideal-verify deletion as 10-min lever (~60–90 s only).

## 9. File map

| Path | Role |
|------|------|
| **This directory** `research/cold-run-10min-1pod/` | **Canonical 1-pod corpus** |
| [`SYNTHESIS.md`](SYNTHESIS.md) | Executive verdict + packages |
| [`FILE-MANIFEST.md`](FILE-MANIFEST.md) | Every report listed |
| [`planning/`](planning/) | ADR cards + decision matrices (swarm) |
| [`00-baseline.md`](00-baseline.md) | Constraints + 3003 s measurement |
| `10`–`29` numbered reports | Code/arithmetic/architecture |
| `05*.md` | Web/DeepSeek/forums/lit forage |
| `research/cold-run-10min/` | **Superseded** dual-pod era (context only) |
| `research/tapetum-llm-speedup/` | Prior 150-agent swarm |
| `research/tapetum-llm-throughput/` | Call census / throughput |
| `packages/whisker/research/deepseek-v4-pro/` | Model-specific notes |

## 10. Quality gates (from `19`)

- Config A = MODERATE single-pod (~23–25 min/run)
- Config B = det-metadata + dense offload (~10–12 min if infra up)
- Ship bar: fleet flip ceiling + dev-replay recall + holdout anchors
- Validation wall ~**0.8–1.2 h** (excludes implementation time)
- Quality pass ≠ ≤600 s; instrumented B ≤620 s required to claim 10 min

## 11. Open risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Dense pods stay down | **Critical** for 10 min | Option C SLA reset |
| Shared multi-tenant noise | HIGH | Off-hours + metrics; double-A |
| Dense judge false-clear/fail | HIGH | 381 gate; escalate ≤15% |
| Payload scoping recall loss | HIGH | Presence index + MoE oversize fallback |
| Thinking still on for JSON | MED | Probe Non-think kwargs (`05q`) |
| MTP assumed free | MED | A/B only; may disable under load |

## 12. Instruction to the planning agent

1. Read `SYNTHESIS.md` + this handoff + `planning/00-DECISION-MATRIX.md` (after swarm lands).
2. Produce a plan with: chosen Option (A/B/C), phased tickets, quality gates, infra asks, and explicit non-goals.
3. Do **not** propose a second V4-Pro or `--max-num-seqs 32`.
4. Cite report IDs (`12`, `17`, `26`, …) for every major claim.
5. If dense restart is uncertain, plan Option A + Option C SLA language in the same doc.
