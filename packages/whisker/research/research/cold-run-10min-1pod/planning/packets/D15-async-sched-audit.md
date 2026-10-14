# D15 — Async-scheduling audit

**Date:** 2026-07-24  
**Status:** Open (ops hygiene)

---

## Decision needed

Audit async scheduling on `alliance-pod` and disable (`--no-async-scheduling`) if the underfill signature is present?

## Recommendation from research

**Yes, audit; disable only on signature.** Signature: `running≈16` + elevated waiting + soft util under client c=32. **Never** raise `--max-num-seqs` to “fix” underfill (S=32 measured +57% wall).

## If yes (audit + conditional disable)

- Restores effective slot use when async scheduling underfills the batch.
- Clear anti-knob: underfill ≠ capacity shortage.
- Measure off-hours with `/metrics` matched occupancy (`28`).

## If no

- Risk leaving S_eff below advertised 16 while operators chase S=32.
- Wall stays inflated by idle-looking GPUs under a full client fan-out.

## Evidence

| Claim | Source |
|-------|--------|
| Underfill → try `--no-async-scheduling`; never raise S | `05s-web-async-sched.md`, ADR-011 |
| S=32 forbidden (+57% wall) | ADR-002, `00-baseline.md` |
| FAQ Q10 / Q41 | `PLANNER-FAQ.md` |
