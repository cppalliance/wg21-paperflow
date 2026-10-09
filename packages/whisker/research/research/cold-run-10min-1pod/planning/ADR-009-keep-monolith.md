# ADR-009: Keep monolith (do not skip)

## Status

**Accepted** — do not skip. Permanent reject for fleet-wide or conditional monolith skip under the 1-pod ≤10 min program unless new evidence meets the reopen bar in `21-skip-monolith-revisit.md`.

## Context

Under single-`alliance-pod` pressure (no twin V4-Pro), the MoE queue becomes monolith-heavy once units/metadata move elsewhere. Heterogeneous design leaves ~381 first-pass monolith calls on MoE; Scenario A wall is MoE-bound ~511 s. That makes "skip monolith when metadata+units suffice" look like a tempting critical-path cut.

Prior dual-pod work already decided **keep monolith** (`research/cold-run-10min/49-monolith-keep.md`). Report `21` re-evaluates under 1-pod ≤600 s pressure and still rejects skip:

| Layout | After full monolith skip | Hits ≤600 s? |
|--------|-------------------------:|:------------:|
| v11 MODERATE, single MoE queue (~1366 s) | ~890 s (−476 s) | No |
| Heterogeneous dense offload (~511 s) | ~352 s (−159 s) | Yes, but 10 min already reachable without skip |

Conditional gates either save ~21 s (safe/narrow) or reopen false-pass history (aggressive ~165/181 PDF skip). Sidecar replay: full skip → 6/378 material fusion deltas via `llm_clear_soft_review`, 8/181 PDF `suggested_verdict` shifts, mono-only `candidate_not_found` on 16 PDF papers, and loss of the only document-wide reorder / TOC-leak lens.

Better MoE cut without deleting that lens: deterministic metadata (−377 calls, ~471 s class) while keeping monolith.

## Decision

1. **Keep monolith** on `alliance-pod` for every paper that reaches the LLM lane (PDF first-pass and HTML tier-1 as today).
2. **Do not** ship fleet-wide monolith skip for speed.
3. **Do not** ship conditional skip when `metadata_outline_check.verdict == pass` and units are scheduled/complete.
4. Prefer call elimination that preserves the document-wide judge (deterministic metadata, verdict-first, router/quota, dense unit offload).
5. Do not reopen skip without meeting the evidence bar in `21` (labeled reorder holdout, or dense-offload A/B still >650 s MoE-bound after det-metadata, with explicit acceptance of fusion deltas).

## Consequences

**Positive**

- Preserves fusion soft-clear axis and mono-only cnf / reorder detection surface.
- 10 min design path (heterogeneous + scoping + parity) does not depend on monolith deletion.
- Aligns with reject ledger and planning constraint C5 (`PLANNING-HANDOFF.md`).

**Negative / cost**

- Under dense offload, monolith remains the MoE bottleneck (~381/428 MoE calls); wall stays MoE-bound until det-metadata and other N/L cuts land.
- Forgoes ~159 s heterogeneous margin (or ~476 s on single MoE queue) that skip would buy at unbounded quality risk.

**Invariants**

- Monolith is not "cheap noise" once units leave the MoE queue; the correct response is shrink MoE N/L, not delete the document-wide judge.
- Out of scope for this program: drop verification / skip monolith as a ≤10 min lever.

## Evidence

| Claim | Source |
|-------|--------|
| Skip monolith = **No** (fusion false-clears; 10 min reachable without) | `SYNTHESIS.md` reject ledger |
| Conditional/fleet skip rejected; keep monolith | `21-skip-monolith-revisit.md` |
| Full skip −476 s single queue / −159 s hetero; still quality-exposed | `21-skip-monolith-revisit.md` |
| 6 fusion material clears; 16 PDF mono-only cnf | `21-skip-monolith-revisit.md`, prior `34-verdict-value-analyst.md`, `147-verifier-monolith-textlane.md` |
| Heterogeneous MoE-bound ~511 s with monolith kept | `12-dense-offload-architecture.md`, `20-heterogeneous-wall.md` |
| Planning C5: no skip monolith as default | `PLANNING-HANDOFF.md` |
| Prior keep decision under dual-pod | `research/cold-run-10min/49-monolith-keep.md` |
