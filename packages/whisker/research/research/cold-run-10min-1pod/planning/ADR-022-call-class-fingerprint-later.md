# ADR-022: Defer call-class fingerprints (0 cold save)

## Status

Deferred — out of cold-run critical path

## Date

2026-07-24

## Context

Today's whole-paper fingerprint hashes all PDF-lane prompts into one `prompt_sha256`. Any single prompt edit invalidates all 381 papers and forces a full cold cascade (~2284 calls, ~3003 s at v10; ~21–25 min post-v11).

Per-call-class fingerprints (`25`) would skip unchanged call classes on **reruns** after a prior fleet (unit-prompt-only edit → re-LLM ~774 calls instead of 2284). On a **true cold** with empty `whisker/llm/` sidecars, every class misses cache: **0 s saved**.

The ≤10 min / 1-pod gap is a first-cold N×L problem, not an iteration-tax problem.

## Decision

1. **Defer** call-class fingerprint work until after cold-path levers land (v11 ship, det-metadata, verdict-first, router/quota; dense cascade if unblocked).
2. Do **not** schedule it as a cold-wall ticket or bank any seconds toward ≤600 s / Option A floors.
3. When resumed: treat as a **dev/ops rerun accelerator** before the next `_LANE_VERSION` or prompt-churn cycle; require guard-tag normalization so per-paper HMAC tags do not poison cache keys (`25`).

## Consequences

**Positive**

- Keeps the 10-min program focused on call elimination and L cuts that move first cold.
- Avoids sidecar schema churn concurrent with det-metadata / dense routing ships.

**Negative / cost**

- Prompt-edit iteration still pays full-fleet invalidation until this lands later.
- Warm whole-paper skip (today) remains the only fast path.

**Falsifiers**

- New evidence that call-class cache hits on first cold (contradicts empty-sidecar model) → reopen.
- Human prioritizes iteration tax over cold SLA → schedule after P3 MoE package, still not as a 10-min lever.

## Evidence

| Claim | Source |
|-------|--------|
| Cold first-run impact **0 s**; rerun-only accelerator | `25-call-class-fingerprint.md` |
| Not on cold path; 0 s greenfield | `SYNTHESIS.md` |
| Fingerprint 0 s on cold after lane bump (related) | `24-det-skip-llm.md`, ADR-010 |
| Warm skip 375/381 in 64.8 s (irrelevant to bare cold) | `00-baseline.md`, `PLANNING-HANDOFF.md` §1 |
