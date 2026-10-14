# SUCCESS-METRICS — 10 min vs 15–20 min SLA

**Date:** 2026-07-24  
**Audience:** planner / ops / stakeholders  
**Sources:** [`SYNTHESIS.md`](../SYNTHESIS.md), [`01-OPTIONS-ABC.md`](01-OPTIONS-ABC.md), [`ADR-018-sla-fork.md`](ADR-018-sla-fork.md), [`QUALITY-PROTOCOL.md`](QUALITY-PROTOCOL.md), [`MEASUREMENT-PROTOCOL.md`](MEASUREMENT-PROTOCOL.md), [`19-quality-gate-1pod.md`](../19-quality-gate-1pod.md), [`17-physics-floor-skeptic.md`](../17-physics-floor-skeptic.md), [`26-dense-pod-liveness.md`](../26-dense-pod-liveness.md)

Two different success declarations. Do not mix them.

| Program | Goal wall | Infra | Quality |
|---------|-----------|-------|---------|
| **10-min success** | Cold fleet **≤600 s** (stretch declare ≤620 s instrumented) | Dense primary **UP** | Full `19` gate pass |
| **15–20 min SLA success** | Cold fleet **≤1200 s** (prefer ≤900–1200 s band) | MoE only OK | No fused-verdict regression vs MODERATE A |

---

## 1. Shared measurement rules (both programs)

From [`MEASUREMENT-PROTOCOL.md`](MEASUREMENT-PROTOCOL.md) and [`SYNTHESIS.md`](../SYNTHESIS.md) (`28`):

1. Full **381** papers, `--force` cold (no warm fingerprint skip for the declaring run).
2. Production client **c=32**, MoE **S=16**; never raise S/c to “make” the SLA.
3. Quiet / off-hours window; log `alliance-pod` `/metrics` (`num_requests_running`, `waiting`) beside wall.
4. Record `_LANE_VERSION`, git SHA, `SERVICES.toml` pins, dense/MoE routing flags.
5. **Do not** declare success from a single noisy run if occupancy was half-stolen (~2× wall risk per `28`). Prefer two quiet walls within ~15% or one quiet + documented `external_in_flight≈0`.

Wall clock = end-to-end client timer for the fleet job (same definition as package rollups in `18`).

---

## 2. 10-minute success (Option B)

**Promise:** ≤10 min cold at quality on one MoE + existing dense ([`SYNTHESIS.md`](../SYNTHESIS.md) heterogeneous design; [`01-OPTIONS-ABC.md`](01-OPTIONS-ABC.md) Option B).

### 2.1 Preconditions (all required)

| # | Gate | Pass criteria | Cite |
|---|------|---------------|------|
| I1 | Dense liveness | `h200-qwen3-32b` **HTTP 200**, model id match, one unit-check completion | `26`, INFRA-ASK |
| I2 | Payload scoping | Scoped unit payloads landed (~10–15k/unit); dense not stuck at negative-EV S≤16 | `23`, `12` |
| I3 | Routing | Units (+ optional metadata) on dense; monolith / HTML tier-1–2 / oversize / ≤15% escalate on MoE | `12` |
| I4 | Quality | `flip_AB ≤ flip_AA + margin`; dev-replay recall; holdout anchors — all per [`QUALITY-PROTOCOL.md`](QUALITY-PROTOCOL.md) | `19` |

If I1 fails → **cannot** declare 10-min success; fork to §3 ([`ADR-018`](ADR-018-sla-fork.md)).

### 2.2 Wall criteria

| Tier | Wall | Meaning |
|------|-----:|---------|
| **Hard success** | **≤600 s** | Meets the named 10-min SLA |
| **Declared success (planning)** | **≤620 s** | Instrumented B claim bar from handoff / Option B kill criteria; still market as “~10 min” only with quality pass and quiet occupancy |
| **Design central** | **~511 s** MoE-bound | Aspirational if 2× dense + scoping + parity (`12`, `20`); not required for declare |
| **Fail** | **>620 s** quiet, or any quality gate fail | Do not claim 10 min; keep MoE package value under §3 language |

AGGRESSIVE bare **~585 s** / realistic **~715–910 s** (`18`, SYNTHESIS) are planning bands, not success by themselves. **715–910 s without a ≤620 s measured quiet B is not 10-min success.**

### 2.3 Declaration checklist

- [ ] I1–I4 all green  
- [ ] At least one quiet full-381 B wall **≤620 s** (prefer ≤600 s)  
- [ ] `call_timings` / metrics show meaningful dense vs MoE split (offload actually ran)  
- [ ] Artifacts stored (equiv scratch + run manifest)  
- [ ] Stakeholder language: “≤10 min cold on MoE+dense” — **not** “one V4-Pro alone”

### 2.4 Explicit non-success

- MoE-only wall in the 12–15 min band (`SYNTHESIS` AGGRESSIVE realistic without live dense path) → **not** 10-min success.  
- Hairline **~585 s** spreadsheet with dense 404 → **not** success.  
- Wall ≤600 s with failed 381 parity → **not** success (fidelity over speed; `19`, CLAUDE fidelity).

---

## 3. 15–20 minute SLA success (Option A + C)

**Promise:** publish and meet **~15–20 min** cold full fleet after the MoE-only package when dense will not unlock 10 min ([`SYNTHESIS.md`](../SYNTHESIS.md) Verdict / Execution §4; [`ADR-018`](ADR-018-sla-fork.md); Option C).

### 3.1 Preconditions

| # | Gate | Pass criteria | Cite |
|---|------|---------------|------|
| S1 | MoE package shipped | v11 short-circuit in the measured lane; plus the agreed Option A stack (det-metadata and/or verdict-first and/or router and/or Tier-1 as enabled) | `10`, `18`, Execution order |
| S2 | Remeasured baseline | Post-v11 cold known; further levers compared to that baseline, not v10 3003 s | SYNTHESIS “What v11 already buys” |
| S3 | Quality floor | No shipping lever that fails its A/B gate; monolith kept; no default `--det-skip` | Reject ledger, `21`, `24` |
| S4 | Dense optional | Dense may stay 404; SLA does **not** require `h200-qwen3-32b` | `26`, ADR-018 |

### 3.2 Wall criteria

| Tier | Wall | Minutes | Meaning |
|------|-----:|--------:|---------|
| **SLA success (primary)** | **≤1200 s** | ≤20 | Meets published upper bound |
| **SLA success (strong)** | **≤900 s** | ≤15 | Hits the tight end of ~15–20 |
| **Honest MODERATE band** | **~1366–1493 s** | ~23–25 | Expected after v11+MODERATE **before** full lever stack (`17`, `18`) — **not** yet SLA success if 15–20 was published |
| **Package progress (non-SLA)** | **~12–15 min** (720–900 s) | | SYNTHESIS MoE-only AGGRESSIVE realistic class — good engineering; still **not** 10-min success |
| **SLA fail** | **>1200 s** quiet after committed MoE package | >20 | Do not publish 15–20; either ship more levers or publish a longer SLA |
| **Baseline fail** | Still **~45–50 min** after claimed v11 SC | | Short-circuit / package not landed (`10`) |

### 3.3 Declaration checklist

- [ ] Stakeholder-facing SLA text set to **~15–20 min** (10-min program stopped or explicitly infra-blocked)  
- [ ] Quiet full-381 cold **≤1200 s** on the shipped MoE lane  
- [ ] Prefer a second confirming run or occupancy log  
- [ ] Quality: MODERATE-or-better equivalence vs pre-lever A for any enabled cut (router/det-metadata gates as applicable)  
- [ ] Language: “one `alliance-pod` MoE @ S=16” — do not imply dense or twin

### 3.4 Relationship to 10-min program

| Event | What to declare |
|-------|-----------------|
| Dense still 404 after N days (ADR-018) | **15–20 min SLA success** is the only available product win; 10-min = blocked |
| Dense returns later + §2 passes | Re-open **10-min success**; 15–20 remains a fallback SLA if B regresses |
| MoE package lands ~12–15 min, dense down | Call it **15–20 SLA success** (strong), never “we hit 10 min” |

---

## 4. Side-by-side declare table

| Question | 10-min success | 15–20 min SLA success |
|----------|---------------|------------------------|
| Wall must be… | ≤600 s (declare ≤620 s) | ≤1200 s (strong ≤900 s) |
| Dense `h200-qwen3-32b` | Required UP | Not required |
| 381 parity / holdout | Required (bundled B) | Required for each shipped cut; full AGGRESSIVE gate if dense used |
| MoE-only ~12–15 min | Fail (wrong program) | Success (strong SLA) |
| MoE-only ~23–25 min MODERATE | Fail | Fail if 15–20 was published; OK as interim milestone only |
| v11 still ~50 min | Fail both | Fail both |

---

## 5. Milestone metrics (not final success)

Track these; do not equate to SLA declare:

| Milestone | Metric | Cite |
|-----------|--------|------|
| v11 landed | Cold ~21–25 min (not ~50) | `10`, SYNTHESIS |
| MODERATE package | ~1366–1493 s central | `18`, `17` |
| Det-metadata | ~−471 s class if A/B green | `13` |
| Dense unblocked | HTTP 200 on primary | `26` |
| Heterogeneous design hit | Quiet B ≤620 s + quality | `12`, `19` |

---

## 6. One-line rules

- **10-min success** = dense UP + quality gate + quiet wall **≤620 s** (hard **≤600 s**).  
- **15–20 min SLA success** = MoE package shipped + quiet wall **≤1200 s** + 10-min claim retired or blocked.  
- If dense returns **200** and 381 A/B **fails** parity → Option B dies; keep §3 SLA ([`FALSIFIERS.md`](FALSIFIERS.md) H3).  
- If v11 cold still **~50 min** → short-circuit not landed; neither success applies ([`FALSIFIERS.md`](FALSIFIERS.md) V1–V2).
