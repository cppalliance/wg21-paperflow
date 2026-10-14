# D24 — Reserve Qwen3.6-27B (not primary)

**Date:** 2026-07-24  
**Status:** Open (after 32B A/B)

---

## Decision needed

Treat `b300-qwen36-27b` as **reserve / latency pilot #2**, not the primary dense unit judge?

## Recommendation from research

**Yes — reserve only.** Primary remains `h200-qwen3-32b` (D02 / ADR-005). Bring up 27B only after 32B A/B passes, or as a parallel latency pilot if 32B holds quality and decode headroom is needed (hypothesis ≥2× decode; higher false-clear risk until proven). Class label stays `qwen3-dense-27-32b`.

## If yes (reserve policy)

- Avoids splitting validation across two unproven dense primaries while pods are scarce.
- Keeps INFRA-ASK focused on 32B restart first.
- 27B can still win a later latency bake-off without blocking Option B design.

## If no (make 27B primary now)

- Dilutes the one restart ask; no public UnitCheck A/B vs V4-Pro for either model yet.
- Risks shipping a smaller spine before 32B parity is known.

## Evidence

| Claim | Source |
|-------|--------|
| Rank 1 = 32B; rank 2 = 27B after A/B | ADR-005, `05f-web-dense-judge-lit.md` |
| Both dense endpoints 404 today | `26-dense-pod-liveness.md` |
| H4 falsifier: 27B only after 32B path | `FALSIFIERS.md` |
