# ADR-023: Reject P/D disaggregation on one 8×H200

## Status

Rejected — do not reopen without new measured evidence

## Date

2026-07-24

## Context

Prefill/decode (P/D) disaggregation is a real serving pattern for long-OSL, multi-node MoE goodput. Our workload on `alliance-pod` is the opposite class: decode-bound short structured JSON (~5.91 s decode vs ~0.46 s prefill; pass-path ~55 tokens), long prompts, S_eff=16, **single** DeepSeek-V4-Pro FP8 replica on 8×H200. Twin / second node is forbidden.

Classic single-node 4P+4D needs a second full weight replica on a GPU subset. DeepSeek FP8 needs the whole 8×H200 per replica; 4×H200 cannot hold a second FP8 copy. Multi-node 1P:N D requires capacity this corpus bans.

## Decision

1. **Do not** pursue P/D disaggregation on `alliance-pod` for the cold-run program.
2. Prefer levers already in scope: call elimination, Non-think / verdict-first decode shrink, APC/prefix, MTP A/B only (unbanked), dense offload when live.
3. Reopen only if a measured A/B on alliance-pod (or identical V4-Pro 8×H200) shows ≥15% per-call wall drop on tapetum unit shapes under S=16 / c=32 **without** a second node, or an official single-node PD recipe keeps one weight replica with documented short-OSL wins (`05k`).

## Consequences

**Positive**

- Avoids high ops cost (proxy, NIXL/MORI, P:D tune) with no deployable topology under the twin ban.
- Prevents false hopes from Qwen-235B / OSL=1000 single-node PD headlines that do not port.

**Negative / cost**

- Forgoes any unproven intra-engine phase-specialization gains (not evidenced for DeepSeek on one 8×H200 short-OSL).

## Evidence

| Claim | Source |
|-------|--------|
| Verdict: no — short OSL; cannot split node | `05k-web-pd-disagg.md` |
| Reject ledger: P/D on one 8×H200 | `SYNTHESIS.md`, `PLANNING-HANDOFF.md` §8, `NON-GOALS.md` |
| Decode-bound phase split; ~55-token outs | `05k-web-pd-disagg.md`, speedup SYNTHESIS via `05k` |
| DeepSeek FP8 needs full 8×H200; multi-node PD | vLLM recipes / AWS PD notes via `05k` |
