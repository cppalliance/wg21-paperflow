# CHECK: Front-end floor 758 calls = 948 s @ S=16

**Claim:** 758 unconditional front-end calls × 20 s / 16 slots = 948 s.
**Source:** `17-physics-floor-skeptic.md`

## Quote

> Front-end only (381 monolith + 377 metadata) | 758 | **948 s**
>
> You cannot reach ≤600 s by trimming units alone: front-end **758 × 20 / 16 = 948 s** exceeds the target before any unit check executes.

## Verdict

**CONFIRMED** — arithmetic and call census match in report 17.
