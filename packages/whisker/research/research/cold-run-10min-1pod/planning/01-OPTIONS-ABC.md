# 01 — Options A / B / C compared

**Date:** 2026-07-24  
**Audience:** downstream planner  
**Sources:** [`PLANNING-HANDOFF.md`](../PLANNING-HANDOFF.md), [`SYNTHESIS.md`](../SYNTHESIS.md), [`18-packages-1pod.md`](../18-packages-1pod.md), [`17-physics-floor-skeptic.md`](../17-physics-floor-skeptic.md), [`12-dense-offload-architecture.md`](../12-dense-offload-architecture.md), [`26-dense-pod-liveness.md`](../26-dense-pod-liveness.md)  
**Hard constraint:** no second DeepSeek-V4-Pro pod; `S_eff=16` on `alliance-pod` forever ([`PLANNING-HANDOFF.md`](../PLANNING-HANDOFF.md) C1–C2).

---

## Snapshot

| | **A — MoE-only** | **B — Heterogeneous dense** | **C — SLA reset** |
|---|---|---|---|
| **Promise** | Ship quality stack; do **not** claim ≤10 min | Design for ≤10 min via `max(T_moe, T_dense)` | Stop the 10-min program; publish ~15–20 min |
| **Goal wall** | ~12–23 min cold (honest band) | ≤600 s (~10 min) | ~15–20 min published SLA |
| **Realistic wall** | MODERATE ~1366–1493 s (~23–25 min); stacked MoE levers plan ~12–15 min, bank **~15–20 min** | **~511 s** MoE-bound if 2× dense + scoping + parity; planning **~510–710 s** | Same as A’s honest floor once MoE package ships |
| **Infra today** | `alliance-pod` **UP** | Dense pods **all 404** — **blocked** ([`26`](../26-dense-pod-liveness.md)) | None beyond MoE |
| **≤600 s?** | **No** ([`17`](../17-physics-floor-skeptic.md), [`18`](../18-packages-1pod.md)) | **Maybe** (design only; infra-dead today) | N/A (goal moved) |

---

## Option A — MoE-only (shippable without infra)

Ship call cuts and decode discipline on `alliance-pod` alone. Twin and dense restart are out of scope for the wall claim.

### Goal wall / realistic wall

| Band | Wall | Source |
|------|-----:|--------|
| **Goal (honest)** | ~12–23 min; **do not promise ≤10 min** | [`PLANNING-HANDOFF.md`](../PLANNING-HANDOFF.md) §4 Option A |
| **MODERATE central** | **~1366 s** (~22–23 min); pess. **~1493 s** (~25 min) | [`18`](../18-packages-1pod.md), [`SYNTHESIS.md`](../SYNTHESIS.md) |
| **Physics floor (quality)** | Front-end only **948 s**; quality MODERATE survivors **~1366–1493 s** | [`17`](../17-physics-floor-skeptic.md) |
| **Honest SLA without dense** | **~15–20 min** after MoE package | [`PLANNING-HANDOFF.md`](../PLANNING-HANDOFF.md) §3, [`SYNTHESIS.md`](../SYNTHESIS.md) |
| **≤600 s** | **Impossible** at quality on one MoE @ S=16 | [`17`](../17-physics-floor-skeptic.md): 758×20/16 = **948 s** before units |

Levers (handoff): v11 short-circuit (landed) → det-metadata → verdict-first → router/quota → server Tier-1. Package rollups: CONSERVATIVE ~2163 s; MODERATE ~1366 s; AGGRESSIVE numbers in [`18`](../18-packages-1pod.md) **include dense offload** and are **not** Option A walls.

### Infra prerequisites

| Item | Status |
|------|--------|
| `alliance-pod` (DeepSeek-V4-Pro, S=16) | **Required and UP** ([`26`](../26-dense-pod-liveness.md) control probe 200) |
| Twin `h200x8-deepseek-v4-pro` | **Forbidden** (C1); also 404 |
| Dense Alliance pods | **Not required** for A |

### Code prerequisites

| Lever | Notes | Cite |
|-------|-------|------|
| Remeasure cold on local v11 | Truth baseline; expect ~21–25 min post short-circuit | [`SYNTHESIS.md`](../SYNTHESIS.md), handoff P0 |
| Ship v11 short-circuit | Metadata Tier A+B already in working tree | handoff P1; [`18`](../18-packages-1pod.md) MODERATE |
| Det-metadata shadow A/B | HTML-first staging then fleet; −~251 then −~471 s class | handoff P2; [`SYNTHESIS.md`](../SYNTHESIS.md) |
| Verdict-first / schema bifurcation | After det-metadata; holdout gate | handoff P3; [`SYNTHESIS.md`](../SYNTHESIS.md) |
| Router `combo_safe` + dynamic `MAX_UNIT_CHECKS` | Holdout 3/381 + 16/381 | handoff §5 |
| Server Tier-1 | MBT 16384, CUDA graphs, DeepEP low-latency (~10–15%); **never** S=32; MTP k=1 A/B only (do not bank) | [`SYNTHESIS.md`](../SYNTHESIS.md), handoff |

### Quality risk

| Risk | Severity | Notes |
|------|----------|-------|
| Det-metadata false skip | HIGH | A/B only; LLM must add nothing material ([`SYNTHESIS.md`](../SYNTHESIS.md) lever #2) |
| Router FN on 16/381 flip papers | HIGH | Holdout required ([`18`](../18-packages-1pod.md) gates) |
| Shared-pod noise | HIGH | Off-hours + `/metrics` matched occupancy (handoff §11, SYNTHESIS `28`) |
| Skipping monolith / default det-skip | Rejected | C5; reject ledger |

Lower semantic risk than B: no judge model swap. Still a lane change when det-metadata or router cuts land → fingerprint / `_LANE_VERSION` discipline.

### Time-to-ship (relative)

**Fastest shippable path.** Code + ops flags only; no Alliance dense restart. Phases P0–P4 in handoff §6. Relative: **A ≪ B** (B blocked on infra + parity); **A ≈ C** on engineering (C is mostly messaging + stopping the 10-min chase).

### When to choose A

- Dense restart is **no / unknown / delayed**, and you still want wall cuts from ~48–50 min baseline.
- Quality-stability is non-negotiable; you refuse dense-judge parity risk for now.
- Twin stays forbidden and you accept that **≤10 min is physics-impossible** on MoE-only ([`17`](../17-physics-floor-skeptic.md)).

### Kill criteria (A)

Stop deepening MoE-only “10 min” claims (or declare A failed for a ≤600 s goal) if:

1. Instrumented MODERATE cold stays **>650 s** gap model intact but stakeholders still demand ≤600 s without dense → pivot to **C** or unblock **B** ([`17`](../17-physics-floor-skeptic.md) “what would change my mind” inverted).
2. Det-metadata or router A/B fails fused-verdict / holdout gates → revert lever; do not stack further N cuts.
3. Someone proposes S=32, c>32, twin, or skip monolith as “A stretch” → **reject permanently** (handoff §8).
4. Measured wall after full MoE stack still marketed as ≤10 min → kill the marketing claim; keep the stack as ~15–20 min product (**C** language).

---

## Option B — Heterogeneous dense cascade (only ≤10 min design)

```
T0 CPU:     det metadata / short-circuit
T1 dense:   unit checks (+ optional metadata LLM) on h200-qwen3-32b
T2 MoE:     monolith, HTML tier-1/2, oversize, escalate ≤15%
```

Wall model: `wall ≈ max(T_moe, T_dense) + T_client` ([`12`](../12-dense-offload-architecture.md), handoff §3).

### Goal wall / realistic wall

| Band | Wall | Source |
|------|-----:|--------|
| **Goal** | ≤600 s (~10 min) | handoff Option B |
| **Central (scoped, 2× dense decode, parallel)** | **~511 s** MoE-bound (`max(~476–511 MoE, ~177–352 dense)`) | [`12`](../12-dense-offload-architecture.md) Scenarios A/C; handoff §3 |
| **Planning band** | **~510–710 s** (if metadata stays on MoE at L=20 → ~620–710) | [`12`](../12-dense-offload-architecture.md), [`SYNTHESIS.md`](../SYNTHESIS.md) |
| **AGGRESSIVE package (queue model + friction)** | Bare **~585 s** / realistic **~715–910 s** | [`18`](../18-packages-1pod.md) — includes dense; friction +130–230 s |
| **Without payload scoping** | Dense **NEGATIVE EV** (~2349 s dense leg @ S≤16, L≈20) | [`12`](../12-dense-offload-architecture.md) Scenario D |
| **Infra today** | **Blocked** — 0/4 dense pods alive | [`26`](../26-dense-pod-liveness.md) |

**Live dense status (2026-07-24, do not invent UP pods):**

| Service | Status |
|---------|--------|
| `h200-qwen3-32b` (primary) | **404** |
| `b300-qwen36-27b` (reserve) | **404** |
| `b200x2-gemma4` | **404** (also avoid as primary judge) |
| `b200-r1` | **404** (also avoid) |
| `alliance-pod` | **UP** |

Heterogeneous Package C / Option B is **infra-dead** until Alliance restarts at least `h200-qwen3-32b` ([`26`](../26-dense-pod-liveness.md), [`SYNTHESIS.md`](../SYNTHESIS.md)).

### Infra prerequisites

1. Alliance restarts **`h200-qwen3-32b`** (minimum); probe `GET /v1/models` → 200 + smoke unit call ([`26`](../26-dense-pod-liveness.md)).
2. Dense vLLM recipe: S=32–48, FP8 KV, prefix caching, MBT 16384 ([`12`](../12-dense-offload-architecture.md) §implementation).
3. MoE stays S=16; client per-pod semaphores (MoE 16, dense 32–48) ([`12`](../12-dense-offload-architecture.md)).
4. Policy permission alone is **not** enough ([`SYNTHESIS.md`](../SYNTHESIS.md)).

### Code prerequisites

| Lever | Role | Cite |
|-------|------|------|
| Payload scoping ~10–15k/unit | **Hard blocker** for dense S≥32 and 2× decode | [`12`](../12-dense-offload-architecture.md), [`SYNTHESIS.md`](../SYNTHESIS.md) |
| Call-class service router | Units/metadata → dense; monolith/esc/oversize → MoE (~428 MoE / ~1879 dense) | [`12`](../12-dense-offload-architecture.md) |
| Oversize preflight | 8 papers → MoE fallback | [`12`](../12-dense-offload-architecture.md) |
| MODERATE short-circuit (+ optional det-metadata) | Margin; wall stays MoE-bound ~511 s even with short-circuit | [`12`](../12-dense-offload-architecture.md) Scenario C |
| Quality gate ~0.8–1.2 h | 381/381 fused parity + equivalence vector + holdouts | handoff §10; [`12`](../12-dense-offload-architecture.md); report `19` |

### Quality risk

| Risk | Severity | Notes |
|------|----------|-------|
| Dense judge false-clear / false-fail | **HIGH** | Semantic lane change; 381/381 + 16 flip-set + zero-defect audit ([`12`](../12-dense-offload-architecture.md)) |
| Payload scoping recall loss | **HIGH** | Presence index + MoE oversize fallback |
| Escalation rate >15% | MED–HIGH | Cascade lit: escalate ≤15% to Pro ([`SYNTHESIS.md`](../SYNTHESIS.md)) |
| Wrong primary (Gemma / R1) | HIGH | Avoid Gemma wording false-fail; avoid R1 thinking overhead ([`12`](../12-dense-offload-architecture.md)) |
| Bundled lane bumps | MED | Do not ship dense + short-circuit + HMAC in one bump without attribution B ([`12`](../12-dense-offload-architecture.md)) |

### Time-to-ship (relative)

**Slowest.** Blocked on ops restart, then scoping → router → bench → **~0.8–1.2 h validation wall** (excludes impl time; handoff §10). Relative: **B ≫ A**; only path that can *claim* ≤10 min after instrumented B ≤620 s ([`SYNTHESIS.md`](../SYNTHESIS.md) / handoff §10).

### When to choose B

- Stakeholders **keep** the ≤10 min SLA.
- Alliance commits to restart **`h200-qwen3-32b`** (date certain).
- Team accepts 381-paper parity gate and payload-scoping work before enable.
- Twin remains forbidden; this is the **only arithmetic ≤10 min candidate** under the ban ([`SYNTHESIS.md`](../SYNTHESIS.md), [`17`](../17-physics-floor-skeptic.md) vs [`12`](../12-dense-offload-architecture.md)).

### Kill criteria (B)

Fail closed / disable dense routing if:

1. Dense pods stay **404** past ops commitment → execute **A + C**; do not ship router to dead proxies ([`26`](../26-dense-pod-liveness.md) false-fail).
2. Scoping not landed and dense runs full-md → **NEGATIVE EV**; kill enablement ([`12`](../12-dense-offload-architecture.md) Scenario D).
3. 381/381 fused parity or 16/381 flip-set equivalence fails → no `_LANE_VERSION` bump ([`12`](../12-dense-offload-architecture.md)).
4. Instrumented heterogeneous cold **>620 s** with matched occupancy → cannot claim 10 min (handoff §10); either add margin levers or **C**.
5. Escalation to MoE systematically **>15%** or dense L fails 2× hypothesis under load → re-bench; do not bank 511 s.
6. Primary drifts to Gemma-4 / R1 without new evidence → kill that primary choice ([`12`](../12-dense-offload-architecture.md)).

---

## Option C — SLA reset

If dense will **not** be restarted and twin stays forbidden: publish **~15–20 min** as the goal; **stop the 10-min program** ([`PLANNING-HANDOFF.md`](../PLANNING-HANDOFF.md) §4 Option C).

### Goal wall / realistic wall

| Band | Wall | Source |
|------|-----:|--------|
| **Published goal** | **~15–20 min** cold full fleet | handoff §3–4; [`SYNTHESIS.md`](../SYNTHESIS.md) |
| **Underlying physics** | Same as A: MODERATE ~23–25 min; MoE stack may improve toward ~15–20 | [`17`](../17-physics-floor-skeptic.md), [`18`](../18-packages-1pod.md) |
| **≤600 s program** | **Abandoned** as a committed deliverable | handoff Option C |

C is not a different compute architecture. It is the honest product/ops outcome of MoE-only + infra refusal.

### Infra prerequisites

None beyond keeping `alliance-pod` healthy. Explicitly **no** dense restart ask as a blocker for “done.”

### Code prerequisites

Optional but recommended: still ship Option A levers (v11, det-metadata, verdict-first, router, Tier-1) so the published ~15–20 min is achievable rather than staying at ~48–50 min baseline. C without A leaves ~50 min reality under a 15–20 min label (false-fail of abandoning MODERATE — [`17`](../17-physics-floor-skeptic.md), [`18`](../18-packages-1pod.md)).

### Quality risk

Lowest *new* risk: no dense judge swap. Residual risk is only whatever A levers you still ship. Organizational risk: stakeholders reopen “10 min” without new infra → churn.

### Time-to-ship (relative)

**Immediate for the decision**; engineering follows A’s schedule if stack still ships. Relative: **C decision ≪ A impl ≪ B**.

### When to choose C

- Alliance will **not** restart dense (or timeline is unbounded).
- Twin stays forbidden.
- Leadership prefers an honest SLA over a blocked ≤10 min design ([`SYNTHESIS.md`](../SYNTHESIS.md): dense down → honest SLA ~15–20 min).
- Often paired with **A** in one plan when dense restart is uncertain (handoff §12.5).

### Kill criteria (C)

1. Dense **`h200-qwen3-32b` returns 200** and ops commits capacity → reopen **B**; retire “10 min abandoned” language.
2. Twin ban lifted with budget → dual-pod MODERATE ~596 s path becomes relevant again ([`18`](../18-packages-1pod.md) dual-pod comparison) — outside this 1-pod corpus’s default plan.
3. Instrumented one-pod MODERATE cold **≤650 s** → physics model error; revisit floors before locking a 15–20 min SLA ([`17`](../17-physics-floor-skeptic.md)).

---

## Cross-option decision tree

```text
Keep ≤10 min SLA?
├─ NO  → Option C (+ usually Option A engineering)
└─ YES → Will Alliance restart h200-qwen3-32b?
         ├─ NO / unknown → Option A + Option C language (handoff §12.5); ≤10 min blocked
         └─ YES (dated)  → Option B (scoping → cascade → 381 gate); fail closed to A/C
```

## Non-negotiable rejects (all options)

Twin V4-Pro · S=32 · c>32 · skip monolith as default · default `--det-skip` · P/D on one 8×H200 · BI mode · bank MTP · Flash without deploy · Gemma-4 primary unit judge · server `guided_grammar` · same-pod MoE→MoE cascade · inventing live dense pods while [`26`](../26-dense-pod-liveness.md) shows **404**.

---

## Citation index

| Claim | Report |
|-------|--------|
| MoE-only cannot hit 10 min; front-end 948 s | [`17-physics-floor-skeptic.md`](../17-physics-floor-skeptic.md) |
| Package walls 2163 / 1366 / 585–715 | [`18-packages-1pod.md`](../18-packages-1pod.md) |
| Heterogeneous ~511 s; scoping blocker; routing split | [`12-dense-offload-architecture.md`](../12-dense-offload-architecture.md) |
| All dense 404; alliance-pod UP | [`26-dense-pod-liveness.md`](../26-dense-pod-liveness.md) |
| Options A/B/C definitions; phases; checklist | [`PLANNING-HANDOFF.md`](../PLANNING-HANDOFF.md) |
| Executive package + live blocker | [`SYNTHESIS.md`](../SYNTHESIS.md) |
