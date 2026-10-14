# ADR-020: Escalate band ≤15% (Option B cascade)

## Status

Proposed — applies only if Option B (heterogeneous dense cascade) is unblocked and pursued

## Date

2026-07-24

## Context

Option B routes unit checks (and optionally metadata) to a dense Alliance endpoint (`h200-qwen3-32b`), keeping monolith / HTML tier-1–2 / page escalations / oversize units on `alliance-pod`. Wall is `max(T_moe, T_dense)`, not the sum. Literature (Jung Cascaded Selective Evaluation, FrugalGPT, AutoMix) supports cheap-first judging with escalate-on-low-confidence; FrugalGPT-class cascades keep ~70–83% of queries off the strong model.

If the escalate fraction grows too large, every escalated unit pays dense latency plus Pro latency, and the MoE queue regrows. At ~30% unit escalate, Pro load can push heterogeneous wall above 600 s even when dense is fast. ADR-003 already sketches escalate triggers; this card fixes the **rate band** as a ship gate for Option B.

## Decision

For Option B unit routing, calibrate and enforce an **escalate-to-Pro band of ≤15%** of dense unit attempts (planning band 10–20%; ship ceiling **15%**).

1. **Dense first** for in-budget unit checks (scoped payloads). Oversize units skip dense and go straight to MoE (count separately from the escalate %).
2. **Escalate → Pro** when any of: invalid/missing schema fields; confidence &lt; λ; empty defect quote on non-pass; dense timeout/5xx after one dense retry. Calibrate λ on holdout so escalate rate ≈10–15% while fused-verdict parity holds.
3. **Instrument** `{accepted_dense, escalated_pro, dense_conf, fused_delta}` as SLOs. Fail closed on band miss: if measured escalate &gt;15% at the parity-passing λ, do not ship the cascade as the ≤10 min path — tighten router, raise dense quality, or abandon Option B rather than silently accept a fat escalate tail.
4. Do **not** same-pod MoE→MoE cascade. Do **not** ABC multi-dense jury on every unit. Do **not** escalate every `review` if fusion already caps; prefer accept-dense vs escalate as two populations with separate p95 tracking.
5. This ADR is inert while dense pods stay 404 (ADR-003 Blocked / ADR-018 fork).

## Consequences

**Positive**

- Keeps Pro queue small enough for MoE-bound ~511 s arithmetic to remain plausible.
- Matches Jung-like strong-tier share and FrugalGPT “most easy units never touch Pro.”
- Gives a numeric ship/no-ship gate alongside 381/381 fused parity.

**Negative / cost**

- λ calibration is empirical; too tight → quality miss, too loose → wall miss.
- Escalate path dominates p95; fleet average can look green while tail regresses — must track escalate-p95 and rate.
- Oversize-direct-to-MoE must not be hidden inside the 15% band (separate counter).

**Falsifiers**

- Measured escalate &gt;25% at any λ that still passes 381/381 parity → cascade EV negative; demote or cancel Option B.
- Escalated set rarely changes fused outcome vs dense → λ too loose or dense already sufficient; retune before shipping.

## Evidence

| Claim | Source |
|-------|--------|
| Option B: dense units, MoE monolith/oversize/escalate ≤15% | `PLANNING-HANDOFF.md` §4, `SYNTHESIS.md` |
| Target escalate ≤15% of dense unit attempts; instrument rates | `05l-web-cascade-papers.md` |
| Jung escalate-on-low-conf; start λ for escalate ≈10–20% | `05l-web-cascade-papers.md`, ADR-003 |
| FrugalGPT ~16.6% reach strong model; escalate band ~15–30% | `05p-web-frugalgpt.md` |
| At ~30% unit escalate, Pro queue can break ≤600 s | ADR-003, `05l-web-cascade-papers.md` |
| Dense false-clear mitigation: escalate ≤15% + 381 gate | `PLANNING-HANDOFF.md` §11 |
| Cascade architecture + triggers | ADR-003, `12-dense-offload-architecture.md` |
