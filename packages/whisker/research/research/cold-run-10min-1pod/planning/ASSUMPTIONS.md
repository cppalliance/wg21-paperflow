# ASSUMPTIONS — Load-bearing claims + falsifiers

**Date:** 2026-07-24  
**Sources:** `SYNTHESIS.md`, `PLANNING-HANDOFF.md`, `12`, `17`, `19`, `26`, `28`, `23` (payload), `05*`.

Each row is an assumption the plan depends on. If falsified, update Option choice and SLA language immediately.

---

## Physics / SLA

| ID | Assumption | How to falsify |
|----|------------|----------------|
| A1 | MoE-only cannot hit ≤600 s at quality-stability on one V4-Pro with S=16 | Land full AGGRESSIVE MoE package (no dense), measure cold 381 ≤600 s **with** quality tiers passing (`19`). Contradicts front-end floor 948 s if front-end call count unchanged (`17`). |
| A2 | Heterogeneous `max(T_moe, T_dense)` is the only ≤10 min arithmetic path under the twin ban | Show a MoE-only measured wall ≤600 s at quality, **or** a third live capacity source not named in `SERVICES.toml`. |
| A3 | Central heterogeneous wall ~511 s (MoE-bound) at 2× scoped dense decode | Bench dense L_unit and MoE monolith queue after scoping; if `max(T_moe, T_dense) > 600` under matched occupancy, Option B misses 10 min. |
| A4 | Without dense restart, honest SLA is ~15–20 min | After MoE package ships, three quiet-window cold runs still ≫20 min, **or** dense returns and Option B lands ≤12 min. |

---

## Infra

| ID | Assumption | How to falsify |
|----|------------|----------------|
| A5 | All dense `SERVICES.toml` endpoints are 404; only `alliance-pod` is up (2026-07-24) | `GET /v1/models` on `h200-qwen3-32b` (or reserve dense) returns **200** with expected model id (`26`, `INFRA-ASK.md`). |
| A6 | Restarting `h200-qwen3-32b` is sufficient primary dense capacity for the cascade | Live pod returns 200 but cannot sustain S=32–48 at scoped shapes, or OOM/preempt keeps L≥20 s (`12` Scenario D). |
| A7 | Twin V4-Pro remains forbidden for this program | Operator rescinds ban and twin is healthy; then dual-pod plan may be reconsidered (out of this corpus until then). |

---

## Dense offload / scoping

| ID | Assumption | How to falsify |
|----|------------|----------------|
| A8 | Payload scoping (~10–15k) is a hard prerequisite; without it dense offload is negative EV | Unscoped full-md dense bench shows S≥32 and L_unit ≤10–12 s sustainably (contradicts `12`/`105`). |
| A9 | ~1502 units + 377 metadata can move to Qwen3-32B; 8 oversize must stay on MoE | Token estimator shows ≫8 papers over 131k×0.80 after scoping, or oversize truncate-and-run on dense passes quality by accident (still a correctness fail). |
| A10 | Dense decode can reach ~2× vs MoE unit latency at scoped shapes | `vllm bench serve` at 12k/256 shows L_unit not ≤10 s (or not ≤8 s at 2.5× claim). |
| A11 | Escalate ≤15% units to MoE keeps quality without blowing MoE queue | Measured escalate rate ≫15% or MoE leg dominates past 600 s after cascade. |
| A12 | Qwen3-32B is acceptable primary; Gemma-4 / R1 are not | 381 gate passes on Gemma primary without wording false-fail (would reopen ranking); or Qwen fails false-clear gate while Gemma passes. |

---

## Quality

| ID | Assumption | How to falsify |
|----|------------|----------------|
| A13 | Four-component equivalence + `flip_AA` margin is the right ship bar (not 0% flip / not strict 381/381) | Product owner mandates exact fused identity; or double-A shows `flip_AA` so high that margin never rejects a broken B. |
| A14 | Dev-replay recall −0.05 and holdout anchors catch dense false-clear that fleet flip misses | Known P0957R8-class omission ships with all three tiers green (protocol hole). |
| A15 | Bundled B (det-metadata + dense) is acceptable for ship despite attribution confound | Gate fails and isolation B is required; then use ~1.8 h debug path (`19` §6.2). |
| A16 | Quality pass ≠ ≤600 s; need wall_B ≤620 s to claim 10 min | Measured B ≤620 s with tiers green (claim OK), or tiers green with wall ≫720 s (fidelity ship, SLA miss). |

---

## Measurement / shared pod

| ID | Assumption | How to falsify |
|----|------------|----------------|
| A17 | `alliance-pod` shared occupancy can ≈2× wall and confound A/B | Three metrics-instrumented cold runs with external_in_flight≈0 show wall variance <5% and stable attribution (`28` “what would change my mind”). |
| A18 | Baseline identical-rerun flip ≥25% at c=32 even without foreign traffic | Double-A at c=32 yields `flip_AA < 5%` on four-component vector without batch-invariant mode. |
| A19 | Off-hours + `/metrics` + double-A are necessary before lever claims | Blind A/B without occupancy match still replicates under later quiet remeasure (weakens, does not kill, the protocol). |

---

## MoE-only levers

| ID | Assumption | How to falsify |
|----|------------|----------------|
| A20 | Post-v11 cold is ~21–25 min, not ~50 min | Remeasure 381 `--force` on working-tree v11; if still ~3000 s, short-circuit inventory is wrong (`10`). |
| A21 | Det-metadata saves ~471 s fleet (HTML staging ~251 s) after A/B | Shadow A/B shows fused verdict changes or wall save ≪ estimate (`13`, `22`). |
| A22 | Verdict-first saves ~124–155 s; router/quota ~190–310 s | Holdout / 3+16 paper gates fail or wall deltas absent (`14`, `15`). |
| A23 | Server Tier-1 alone cannot reach 10 min (~422 s post-SC still ~25 min class) | Ops flags alone produce measured ≤600 s at quality without dense/det-metadata. |
| A24 | MTP / DBO / BI / S=32 must not be banked | Controlled A/B shows large durable wall win without quality loss (reopen case-by-case; BI still fights speed). |

---

## Program structure

| ID | Assumption | How to falsify |
|----|------------|----------------|
| A25 | Skip monolith / default `--det-skip` are unnecessary for 10 min | Show 10 min **only** achievable by dropping monolith **and** quality tiers still pass (`21`, `24`). |
| A26 | Distill is a backup iff scoped dense + short tokens fail the 381 gate | Dense path passes gate (distill deferred) or fails gate and distill recovers recall (`05g`). |

---

## Quick use

Before locking Option B as the committed plan, re-probe **A5**. Before claiming 10 min, falsify checks on **A3**, **A8**, **A10**, **A16**. Before trusting any single cold number on `alliance-pod`, apply **A17–A19**.
