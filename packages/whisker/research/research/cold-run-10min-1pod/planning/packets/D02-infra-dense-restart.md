# D02 — Infra: restart dense Alliance pod

**Date:** 2026-07-24  
**Status:** Open (Alliance ops)

---

## Decision needed

Ask Alliance ops to restart at least **`h200-qwen3-32b`** (primary dense unit judge), and when?

## Recommendation from research

**Yes, ask now.** Minimum ask: bring up `h200-qwen3-32b` to 200 on `/v1/models` plus one unit-check smoke. Reserve `b300-qwen36-27b` after A/B; do **not** prioritize Gemma-4 or R1 as primary. Twin V4-Pro stays forbidden even if it comes back.

## If yes (ops restarts dense)

- Unblocks Option B: ~1879 calls can leave the MoE queue; wall ≈ max(MoE, dense).
- Enables payload-scoping benches, cascade pilot, and quality gate Config B.
- Ops cost: RunPod dense pod uptime; smoke + health in SERVICES inventory.

## If no (dense stays down)

- Heterogeneous Package C stays **infra-dead**; ≤10 min remains impossible at quality.
- Execute MoE-only path only; treat D01 as SLA reset (~15–20 min).
- All ~2284 / post-v11 ~1419 calls stay on `alliance-pod` at S=16.

## Evidence

| Claim | Source |
|-------|--------|
| All four dense endpoints HTTP 404; alliance-pod UP | `26-dense-pod-liveness.md` (2026-07-24 probe) |
| Primary dense = Qwen3-32B; avoid Gemma-4 / R1 primary | `ADR-005`, `12`, `05f` |
| Routing split ~428 MoE / ~1879 dense | `12-dense-offload-architecture.md` |
| Policy permission alone insufficient | `SYNTHESIS.md` live blocker |
