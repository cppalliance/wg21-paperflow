# CROSS-CORPUS-INDEX — Prior research → cold-run-10min-1pod

**Date:** 2026-07-24  
**Canonical corpus:** `research/cold-run-10min-1pod/`  
**Purpose:** Map earlier trees to what planners may still trust vs what this corpus supersedes for *execution*.

Rule of thumb: evidence (measurements, call census, slot physics) usually stays valid. Plans that assume a twin V4-Pro, bank MTP wall seconds, or treat dense pods as live without probing are superseded.

---

## Authority ladder

| Rank | Corpus / artifact | Role for planners |
|-----:|-------------------|-------------------|
| 1 | `research/cold-run-10min-1pod/` (`SYNTHESIS.md`, `PLANNING-HANDOFF.md`, this `planning/`) | **Executable** plan under twin-ban |
| 2 | Live probes in 1-pod cards (`26`, `28`, alliance `/metrics`) | Infra truth as of 2026-07-24 |
| 3 | `research/cold-run-10min/` | Dual-pod-era delta; **context only** for execution |
| 4 | `research/tapetum-llm-speedup/` | Jul-23 swarm: waste diagnosis + lever inventory |
| 5 | `research/tapetum-llm-throughput/`, `slots-32-regression/`, `concurrency-381/` | Concurrency / call-volume physics |
| 6 | `packages/whisker/research/deepseek-v4-pro/` | Model behavior / serving quirks (not wall packages) |

When numbers disagree, prefer 1-pod `SYNTHESIS.md` + cited 1-pod report IDs over older package rollups.

---

## Corpus map

### A. `research/cold-run-10min-1pod/` (this tree) — CANONICAL

| Still valid | Notes |
|-------------|-------|
| Twin V4-Pro **forbidden**; `S_eff=16`; client `c≤32` | Hard constraints C1–C3 |
| MoE-only cannot hit ≤600 s at quality | Physics floor `17`; packages `18` |
| Heterogeneous `wall = max(T_moe, T_dense)` ~511 s MoE-bound | Only ≤10 min *design* path (`12`, `20`) |
| Dense pods all HTTP 404 today | Live blocker `26` |
| MTP / Flash / DBO / think-off forage | `05j`, `05b`, `05z`, `05t`, … — see `CONFLICTS.md` |
| Quality gate ~0.8–1.2 h for AGGRESSIVE bundle | `19` |

**Supersedes:** any dual-pod ship plan as the default execution path.

---

### B. `research/cold-run-10min/` — SUPERSEDED FOR EXECUTION

Prior dual-pod plan (same day, earlier constraint set). Twin revive was the recommended Path A.

| Claim / artifact | Status under 1-pod |
|------------------|--------------------|
| Path A: revive twin → MODERATE ~596 s | **Superseded for execution** (twin forbidden). Keep as historical “what dual-pod would buy.” |
| Path B: single-pod MODERATE ~1490 s / ~25 min | **Still valid** order of magnitude; refined as ~1366–1493 s post-v11 in 1-pod `11`/`18`. |
| Dense-judge offload as Path B alternative | **Still valid direction**; refined into Package C / Option B (`12`). Assumed pods “live” → **overridden** by `26`. |
| Day-0 remeasure v11 (~21–25 min) | **Still valid** |
| Metadata short-circuit / v11 inventory (`10-impl-status-auditor.md`) | **Still valid**; mirrored in `10-impl-status-1pod.md` |
| Server recipe / DeepEP / Non-think notes (`05a`, `40`, `26-server-ops`) | **Mostly valid**; 1-pod `16` + `05t`/`05s` are the ops checklist to cite |
| MTP “modest win, A/B” (`05d`) | **Narrowed** by 1-pod `05j` (short JSON @ c≈16 → do not bank). See `CONFLICTS.md` |
| Dual-pod shard design (`67`, `45`) | **Out of scope** unless twin ban lifts |
| Quality gate for short-circuit + HMAC + dual-pod (`25`) | **Superseded protocol** → use `19-quality-gate-1pod.md` |

**Planner instruction:** Do not re-open dual-pod as the default. Cite this tree only for shared evidence (call waste, v11 status, ops flags).

---

### C. `research/tapetum-llm-speedup/` (2026-07-23, ~150 agents)

Root diagnosis of the 48 min cold wall.

| Topic | Still valid | Superseded / outdated |
|-------|-------------|------------------------|
| Baseline ~2883–3003 s, ~2284 calls, L≈20 s, S=16, c=32 | Yes | — |
| 44.6% fusion-dead unit calls after metadata fail/review | Yes (v11 short-circuit targets this) | Wall after v11 must be remeasured; do not plan from 3003 s as “current” |
| Random guard tag kills prefix reuse; HMAC fix | Yes | Partial land in v11 (PDF); HTML gap still open |
| Decode waste on pass path / verdict-first | Yes | Still unimplemented at HEAD |
| Dual-pod ~1.9× in CONSERVATIVE/MODERATE packages (~596 s central) | Arithmetic if twin existed | **Package tables superseded** — dual-pod removed from 1-pod CONSERVATIVE (`18`) |
| “Pod: 1×H200” in SYNTHESIS header | — | **Wrong shape** — Alliance already 8×H200 TP8+EP (`cold-run-10min` §4); still one *replica* / S=16 |
| Docling 3.8 pages/s / olmocr dense extraction | Valid as *different workload* | Not a Flash or MoE multiplier for tapetum |
| Distill unit-check → small dense (6–12 weeks) | Long-term yes | Only after Path F / dense cascade fails gate (`05g`) |
| MTP listed inside MODERATE package | A/B-gated even then | **Do not bank** per 1-pod `05j` |
| AGGRESSIVE ~300–500 s with dense offload | Directionally | Replaced by ~715 s realistic MoE+AGGRESSIVE / ~511 s heterogeneous (`SYNTHESIS`) |

**Keep citing:** personas on short-circuit (P145), prefix (P149), monolith keep, quality A/A floor, `105-vllm-dense-judge-throughput`, `23-small-judge-evaluator`, `131` det-metadata.

---

### D. `research/tapetum-llm-throughput/`

| Still valid | Superseded |
|-------------|------------|
| Regression is **call volume** (~6 calls/paper), not lost client batching | Dual-pod listed as “allowed-with-conditions” — now **forbidden** for V4-Pro twin |
| No-source-packet unit slot waste | Still actionable code hygiene |
| c>32 and S=32 off the table | Reinforced by 1-pod C2/C3 |
| Prefix caching / APC direction | Still ops-relevant; APC already healthy in speedup probes |

---

### E. `research/slots-32-regression/`

| Still valid | Notes |
|-------------|-------|
| Server `--max-num-seqs 32` **+57–60% wall** vs 16 | Non-negotiable; 1-pod forbids S>16 |
| Optimal proven: **server 16 + client c=32** | Unchanged |
| MoE expert-union bandwidth story | Still the causal model |

**Nothing superseded** — this is load-bearing physics for C2.

---

### F. `research/concurrency-381/`

| Still valid | Notes |
|-------------|-------|
| Client c=381 / unbounded burst → RunPod/proxy timeouts | Forbids c>32 (C3) |
| httpx 600 s read + paper 900 s wrapper interaction | Tail-risk context for any future concurrency experiment |
| Batch alternatives / vLLM HTTP limits cards | Background only |

**Nothing to re-litigate** for the 10 min program.

---

### G. `packages/whisker/research/deepseek-v4-pro/`

Model-fit research (Jul 2026), not a cold-wall package.

| Still valid for planners | Out of scope / do not misuse |
|--------------------------|------------------------------|
| V4-Pro as open-weight judge; schema-in-prompt + retries | Wall arithmetic (use 1-pod cards) |
| 94% hallucination-when-wrong / abstention failure → grounding + pass-demotion gap | Treat as quality risk for Flash/dense swaps |
| Serving: `deepseek_v4` tokenizer/reasoning/tool parsers; vLLM version watchlist | Confirm on alliance-pod image |
| Long-context inflection ~128K; text-only (no vision) | Images already operator out-of-scope |
| MoE routing variance on shared pod | Reinforced by 1-pod `28` shared-pod noise |
| Tapetum lane-fit (`14`) axes | Useful for dense/Flash quality gates, not for twin revival |

Freshness addendum (2026-07-02) is older than the cold-run forage; prefer 1-pod `05*` for MTP/Flash/think-off latency priors.

---

## Lever continuity (what survived the twin ban)

| Lever | Origin | 1-pod status |
|-------|--------|--------------|
| Metadata short-circuit (fail+review) | speedup / cold-run-10min | Landed v11 WT; remeasure |
| HMAC + document-last reorder | speedup | Partial; finish HTML |
| LJF / `to_thread` / monolith timeout | speedup | Landed |
| Tombstone fingerprints | speedup / throughput | Landed (warm win) |
| Verdict-first / pass-path slim | speedup MODERATE | Still to build |
| Router combo_safe + dynamic quota | cold-run-10min / 1-pod `14` | Still to build; holdout gates |
| Deterministic metadata | speedup AGGRESSIVE / 1-pod `13` | A/B only; HTML-first staging |
| Dense unit offload | speedup AGGRESSIVE / cold-run-10min Path B | **Primary ≤10 min path**; blocked on `26` |
| Dual-pod V4-Pro shard | speedup CONSERVATIVE | **Forbidden** |
| MTP k=1 | speedup MODERATE / cold-run `05d` | Ops A/B only; **not banked** |
| Server MBT 16384, DeepEP low-latency, CUDA graphs | cold-run ops | Tier-1 yes; DBO usually flat @ seqs=16 |
| Distill small dense judge | speedup §6 / `05g` | Parallel program if cascade fails |

---

## Quick “open which file” guide

| Planner question | Open first |
|------------------|------------|
| Can we hit 10 min? | `../SYNTHESIS.md`, `../17-physics-floor-skeptic.md` |
| Twin vs dense vs SLA reset | `../PLANNING-HANDOFF.md` Options A/B/C |
| Slot / wall math | `../11-wall-arithmetic-1pod.md`, `../20-heterogeneous-wall.md` |
| Dense routing split | `../12-dense-offload-architecture.md` |
| Are dense pods up? | `../26-dense-pod-liveness.md` |
| S=16 forever? | `research/slots-32-regression/SYNTHESIS.md` |
| Why not c=381? | `research/concurrency-381/` |
| Why 48 min originally? | `research/tapetum-llm-throughput/SYNTHESIS.md` |
| Model quality risks | `packages/whisker/research/deepseek-v4-pro/SYNTHESIS.md` |
| Contradictory numbers | [`CONFLICTS.md`](CONFLICTS.md) |

---

## Explicit non-citations for execution plans

Do not treat as current ship design:

- Dual-pod MODERATE central **~596 s** as the committed path (`tapetum-llm-speedup` / `cold-run-10min` SYNTHESIS).
- CONSERVATIVE package tables that **include** dual-pod shard.
- “Four live dense pods” from inventory-only reads (`cold-run-10min/16-dense-judge-candidates.md` without `26`).
- Banking **MTP** or **Flash 3.8×** wall cuts without deployment + A/B.
- Docling/olmocr page/s as MoE-judge speed priors.
