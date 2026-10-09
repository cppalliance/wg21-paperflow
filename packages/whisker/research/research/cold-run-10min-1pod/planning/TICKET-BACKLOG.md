# TICKET-BACKLOG — Cold-run ≤10 min (1 MoE pod)

**Date:** 2026-07-24  
**Sources:** [`PLANNING-HANDOFF.md`](../PLANNING-HANDOFF.md) §6 phases, [`10-impl-status-1pod.md`](../10-impl-status-1pod.md)  
**Hard constraints:** no twin V4-Pro; MoE `S_eff=16`; quality-stability (fused verdict parity).  
**No implementation code in this file** — tickets only.

Phases follow the handoff order. Option A (MoE-only) ships through P4 without dense. Option B (≤10 min candidate) needs P5–P7. Option C (SLA reset ~15–20 min) is the exit if dense stays down.

---

## Summary matrix

| ID | Title | Phase | Depends | Effort | Blocked-by-infra? |
|----|-------|-------|---------|:------:|:-----------------:|
| CR-P0-REMEASURE | Remeasure cold fleet on local v11 | P0 | — | S | N |
| CR-P1-SHIP-V11 | Commit/ship v11 short-circuit + finish partial v11 hygiene | P1 | CR-P0-REMEASURE | M | N |
| CR-P2-DET-META | Deterministic metadata/outline diff (HTML-first → fleet) | P2 | CR-P1-SHIP-V11 | L | N |
| CR-P3-VERDICT | Verdict-first / terse pass schema bifurcation | P3 | CR-P1-SHIP-V11 | M | N |
| CR-P3-ROUTER | Router `combo_safe` + dynamic `MAX_UNIT_CHECKS` | P3 | CR-P1-SHIP-V11 | M | N |
| CR-P4-SERVER | Alliance-pod Tier-1 server flags (ops) | P4 | CR-P0-REMEASURE | S | N |
| CR-P5-DENSE-ASK | Alliance ask: restart dense pod (`h200-qwen3-32b`) | P5 | — (parallel with P0–P4) | S | Y |
| CR-P6-PAYLOAD | Payload scoping for dense unit/metadata windows | P6 | CR-P1-SHIP-V11 | L | N |
| CR-P6-CASCADE | Call-class cascade router (dense units + MoE fallback) | P6 | CR-P5-DENSE-ASK, CR-P6-PAYLOAD | L | Y |
| CR-P7-QG | Quality gate: Config A/B fleet parity (`19`) | P7 | CR-P2-DET-META, CR-P6-CASCADE; recommend CR-P3-* | M | Y |
| CR-P8-FINGERPRINT | Call-class fingerprints (iteration ops; later) | P8 | CR-P1-SHIP-V11 | M | N |
| CR-P8-DISTILL | Distill / smaller judge program (only if P7 fails) | P8 | CR-P7-QG (fail path) | L | Y |

---

## P0 — Truth baseline

### CR-P0-REMEASURE — Remeasure cold fleet on local v11

| Field | Value |
|-------|-------|
| **Phase** | P0 |
| **Depends** | — |
| **Effort** | S |
| **Blocked-by-infra?** | N (`alliance-pod` UP) |

**Acceptance criteria**

- One full-fleet cold run (`381` papers, `--force`) on working-tree `_LANE_VERSION = 11`, single `alliance-pod`, `S_eff=16`.
- Wall time recorded with matched occupancy notes (`/metrics` or off-hours protocol from `28`).
- Result lands in the expected band **~1260–1493 s (~21–25 min)**; if ≤700 s without dense, reopen L_abs / short-circuit accounting (`10` “What would change my mind”).
- Sidecar / trace artifacts retained for later A/A noise floor.

**Evidence reports:** `00`, `10`, `11`, `28`

---

## P1 — Ship landed levers

### CR-P1-SHIP-V11 — Commit/ship v11 short-circuit + finish partial v11 hygiene

| Field | Value |
|-------|-------|
| **Phase** | P1 |
| **Depends** | CR-P0-REMEASURE (confirm arithmetic before treating HEAD as baseline) |
| **Effort** | M |
| **Blocked-by-infra?** | N |

**Acceptance criteria**

- Metadata-fail short-circuit (PDF + HTML), LJF ordering, monolith timeouts, empty-packet pre-filter, error tombstones are the committed ship baseline (`10` levers 1, 4–8).
- Partial v11 hygiene closed or explicitly deferred with owners: text-lane HMAC `guard_tag`, candidate-md-first on remaining paths, monolith/metadata prompt reorder (`10` levers 2–3, Tier 2).
- `_LANE_VERSION` / release notes state what is in vs deferred; no twin-pod or `S=32` flags.
- Post-ship cold expectation remains **~21–25 min**, not ≤10 min.

**Evidence reports:** `10`, `00`, `21` (reject skip-monolith default)

---

## P2 — Deterministic metadata

### CR-P2-DET-META — Deterministic metadata/outline diff (HTML-first → fleet)

| Field | Value |
|-------|-------|
| **Phase** | P2 |
| **Depends** | CR-P1-SHIP-V11 |
| **Effort** | L |
| **Blocked-by-infra?** | N |

**Acceptance criteria**

- Shadow A/B: HTML-first staging, then PDF/fleet; `compare_metadata_outline()` (or equivalent) replaces LLM `run_metadata_outline_check` only after gates pass.
- Offline replay vs stored `metadata_outline_check` on 381 sidecars: ≤5% metadata verdict drift **and** zero fused-verdict changes before promotion (`13`).
- Fold semantics match today’s fail/review caps and preserve v11 short-circuit behavior.
- Expected wall cut when shipped: **~−471 s** (377 metadata LLM calls @ S=16); still MoE-only >600 s.

**Evidence reports:** `13`, `10`, `19` (pre-B offline check)

---

## P3 — Decode + router stack

### CR-P3-VERDICT — Verdict-first / terse pass schema bifurcation

| Field | Value |
|-------|-------|
| **Phase** | P3 |
| **Depends** | CR-P1-SHIP-V11 (can parallel CR-P2 after ship) |
| **Effort** | M |
| **Blocked-by-infra?** | N |

**Acceptance criteria**

- Pass-path micro-schema (e.g. `UnitCheckClear` → defect path) lands with finite retries / structured output; no free-text parse.
- 48-anchor holdout ≥95% verdict stability; optional `max_tokens` shrink gated the same way (`15`, `10`).
- Central wall estimate after this lever alone still **>600 s** (~1240 s stack row in `10`); documented as MODERATE, not 10-min closer.

**Evidence reports:** `15`, `10`, `11`

### CR-P3-ROUTER — Router `combo_safe` + dynamic `MAX_UNIT_CHECKS`

| Field | Value |
|-------|-------|
| **Phase** | P3 |
| **Depends** | CR-P1-SHIP-V11 (pair with CR-P3-VERDICT for stack A/B) |
| **Effort** | M |
| **Blocked-by-infra?** | N |

**Acceptance criteria**

- `combo_safe` tightening and/or dynamic quota (not blind static cap-3 fleet-wide) implemented behind holdout gates.
- Holdout must cover **3/381** unit-cap-driver papers and **16/381** LLM-flip equivalence set (`14`).
- Safe harvest target **~150–220** post-v11 survivor calls (~190–310 s); do not claim full ~289 fusion-dead cut without zero regression on those sets.
- If bundled into Config B quality run, confound is accepted per `19`.

**Evidence reports:** `14`, `10`, `19`

---

## P4 — Server ops (MoE)

### CR-P4-SERVER — Alliance-pod Tier-1 server flags

| Field | Value |
|-------|-------|
| **Phase** | P4 |
| **Depends** | CR-P0-REMEASURE (honest before/after L) |
| **Effort** | S |
| **Blocked-by-infra?** | N (ops on live MoE; no dense required) |

**Acceptance criteria**

- Confirm/apply Tier-1 recipe on `alliance-pod` only: prefix caching, `--max-num-batched-tokens 16384`, V4 tokenizer/reasoning parser as applicable; **keep `--max-num-seqs 16`** (`16`, `10` Tier 3).
- Optional A/B only (do not bank): DeepEP low-latency, DBO, MTP k=1 (`16`, handoff reject ledger).
- Forbidden permanently without new evidence: `S=32`, `c>32`, batch-invariant mode, P/D on one 8×H200, guided_grammar.
- Documented L cut only; server ops alone do **not** claim ≤10 min.

**Evidence reports:** `16`, `05c`, `05d`, `05t`, `00`

---

## P5 — Infra ask (Option B prereq)

### CR-P5-DENSE-ASK — Alliance ask: restart dense pod

| Field | Value |
|-------|-------|
| **Phase** | P5 |
| **Depends** | — (start in parallel with P0–P4; blocks P6 cascade + P7 Option B) |
| **Effort** | S |
| **Blocked-by-infra?** | Y |

**Acceptance criteria**

- Written ask to Alliance/ops to bring up primary dense endpoint **`h200-qwen3-32b`** (alternates only after primary A/B): `GET /v1/models` → **200** with expected model id (`26`).
- Probe log stored; twin `h200x8-deepseek-v4-pro` remains **out of scope / forbidden**.
- If restart refused or indefinite: record Option C SLA language (**~15–20 min**) and stop promising ≤600 s (`PLANNING-HANDOFF` §3–4).
- Liveness is a hard gate for CR-P6-CASCADE and CR-P7-QG Config B.

**Evidence reports:** `26`, `12`, `27`, handoff §7

---

## P6 — Heterogeneous enablers

### CR-P6-PAYLOAD — Payload scoping for dense unit/metadata windows

| Field | Value |
|-------|-------|
| **Phase** | P6 |
| **Depends** | CR-P1-SHIP-V11 (code can land before dense is live) |
| **Effort** | L |
| **Blocked-by-infra?** | N (implementation); value unrealized until dense UP |

**Acceptance criteria**

- Unit LLM prompts scoped to ~10–15k tokens (presence index + H2 window ± neighbors); post-hoc grounding still on full candidate md (`23`).
- Oversize / miss path falls back to MoE full payload; no silent drop of units.
- Holdout shows no material recall loss from dehyphenation / index misses (`10`, `23`).
- Explicitly enables dense `S=32–48`; without scoping, dense offload is negative EV.

**Evidence reports:** `23`, `12`, `10`

### CR-P6-CASCADE — Call-class cascade router (dense units + MoE fallback)

| Field | Value |
|-------|-------|
| **Phase** | P6 |
| **Depends** | CR-P5-DENSE-ASK (live dense), CR-P6-PAYLOAD |
| **Effort** | L |
| **Blocked-by-infra?** | Y |

**Acceptance criteria**

- Routing split per `12`: units (+ optional metadata LLM if det-meta not yet shipped) → dense; monolith, HTML tier-1/2, page escalation, oversize units, ideal-verify → MoE.
- Escalate-to-MoE budget ≤15%; `_LANE_VERSION` bump when semantics change.
- Heterogeneous wall model documented as `max(T_moe, T_dense) + T_client`; MoE-bound target band ~511–715 s depending on stack (`12`, `11`, `17`).
- No same-pod MoE→MoE cascade; no Gemma-4 as primary unit judge (`12`, reject ledger).

**Evidence reports:** `12`, `20`, `23`, `26`, `10`

---

## P7 — Ship or fail closed

### CR-P7-QG — Quality gate: Config A/B fleet parity

| Field | Value |
|-------|-------|
| **Phase** | P7 |
| **Depends** | CR-P2-DET-META, CR-P6-CASCADE; recommend CR-P3-VERDICT + CR-P3-ROUTER in Config A/B as applicable |
| **Effort** | M (protocol design/ops); wall clock ~0.8–1.2 h validation |
| **Blocked-by-infra?** | Y (Config B needs live dense) |

**Acceptance criteria**

- Config A = MODERATE single-pod baseline (~23–25 min/run); A/A establishes `flip_AA` (`19`).
- Config B = det-metadata + dense offload (+ optional router) in **one** bundled B run; three gates: fleet flip ceiling, dev-replay recall, holdout anchors (`19`).
- Quality pass ≠ ≤600 s claim; instrumented B ≤620 s required to claim 10 min (`19`, handoff §10).
- Fail closed: do not ship dense offload on wall-looking success without 381 parity (false-pass hypothesis in `10`).

**Evidence reports:** `19`, `10`, `12`, `13`

---

## P8 — Later / contingency

### CR-P8-FINGERPRINT — Call-class fingerprints (iteration ops; later)

| Field | Value |
|-------|-------|
| **Phase** | P8 (deferred; not on cold critical path) |
| **Depends** | CR-P1-SHIP-V11; prefer after P2–P3 prompt/schema churn settles |
| **Effort** | M |
| **Blocked-by-infra?** | N |

**Acceptance criteria**

- Per-call-class prompt/schema hashes so a unit-only edit does not invalidate monolith/metadata sidecars (`25`).
- Cold first-run impact **0 s** on empty cache — must not be sold as a 10-min lever.
- Ships as ops/iteration tax cut before the next heavy `_LANE_VERSION` / prompt churn cycle.

**Evidence reports:** `25`, `10`

### CR-P8-DISTILL — Distill / smaller judge program (only if P7 fails)

| Field | Value |
|-------|-------|
| **Phase** | P8 |
| **Depends** | CR-P7-QG fail path (quality or wall) |
| **Effort** | L |
| **Blocked-by-infra?** | Y (training/serving capacity) |

**Acceptance criteria**

- Opened only if Option B fails quality gate or dense stays unavailable and Option C SLA is unacceptable.
- Parallel research program; not a substitute for P0–P4 Option A shipping.
- Must preserve quality-stability contract; no silent recall trade for wall.

**Evidence reports:** handoff §6 P8, `12`, `19`, `29`

---

## Dependency sketch

```text
CR-P0-REMEASURE ──► CR-P1-SHIP-V11 ──┬──► CR-P2-DET-META ──────────────┐
                                     ├──► CR-P3-VERDICT ──┐             │
                                     ├──► CR-P3-ROUTER ───┤             │
                                     └──► CR-P6-PAYLOAD ──┤             │
CR-P0-REMEASURE ──► CR-P4-SERVER                          │             │
CR-P5-DENSE-ASK ──────────────────────────► CR-P6-CASCADE ┴──► CR-P7-QG
CR-P1-SHIP-V11 ──► CR-P8-FINGERPRINT (later)
CR-P7-QG (fail) ──► CR-P8-DISTILL
```

---

## Non-goals (do not ticket)

Twin V4-Pro · MoE `S=32` · client `c>32` · skip monolith as default · default `--det-skip` · P/D on one 8×H200 · `VLLM_BATCH_INVARIANT` · bank MTP seconds · guided_grammar · same-pod MoE→MoE cascade · ideal-verify deletion as primary 10-min lever · images/VLM.

See handoff §8 reject ledger and `NON-GOALS.md` (when filled).
