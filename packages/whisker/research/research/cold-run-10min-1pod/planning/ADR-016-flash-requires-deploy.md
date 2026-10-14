# ADR-016: Flash unit-judge requires a deploy (reject without endpoint)

**Status:** Accepted — reject Flash as a cold-run wall lever until a Flash endpoint or weight swap exists.

**Date:** 2026-07-24

---

## Context

DeepSeek-V4-Flash (284B / 13B active, MIT, HF `deepseek-ai/DeepSeek-V4-Flash`) is a credible fast unit-check candidate for short structured verdicts. vLLM serves the V4 family; public weights exist.

`SERVICES.toml` today lists only `deepseek-v4-pro` on `alliance-pod` / `h200x8-deepseek-v4-pro`. There is **no** Alliance Flash deployment. Twin Pro is forbidden; Flash is not a software switch on the current Pro pod.

Hosted decode priors (Artificial Analysis DeepSeek first-party, ~72h median, 2026-07-24): Flash non-think **111 tok/s** vs Pro **66 tok/s** → **~1.68×** (~central **1.7×**). Same-host Fireworks OpenRouter band ~1.45×. Active-param ratio 49B/13B ≈ 3.8× overstates the decode win; measured Flash decode prior is **~1.7×**, not 4×. Think on/off still dominates wall versus model tier at fixed think mode.

---

## Decision

**Accept reject:** do not bank Flash wall savings in the ≤10 min / 1-pod plan while Flash is undeployed.

| Path | Verdict |
|------|---------|
| Flash as unit-judge **candidate** (quality/speed) | Yes, after deploy + A/B |
| Flash in cold-run arithmetic **today** | **No** — L savings = 0 without an endpoint |
| Swap `alliance-pod` → Flash weights | Out of band; loses Pro ceiling for fusion/hard on the only MoE node |
| New Flash vLLM endpoint (spare GPUs / non-Pro box) | Allowed as non-twin capacity; still ops + budget, not free |
| Prefer Flash over live dense restart for units | No — dense class (`h200-qwen3-32b`) is the heterogeneous design; Flash is optional parallel track |

When Flash **is** deployed and A/B clears fail-closed quality: use Flash High/Max + escalate hard units to Pro; do not treat Flash Non-think as free speed. Planning prior for decode-bound L at same think mode:

```
L_decode_Flash ≈ L_decode_Pro / 1.7
```

Do **not** scale wall by 49/13. Do **not** import Together/Fireworks peak tok/s as alliance-pod priors.

---

## Consequences

**Positive**

- Keeps the plan honest: undeployed Flash cannot close residual wall.
- Anchors any future Flash EV to the measured **~1.7×** decode prior and to think-mode routing (think budget >> model tier for `L_eff`).
- Avoids false-passing a Flash swap that displaces the only Pro pod without an escalate path.

**Negative / constraints**

- Forgoes a possible ~30–35% E2E cut vs Pro at fixed think mode until ops ships Flash or a weight swap is explicitly approved.
- Flash Max trails Pro on Terminal-Bench-like agentic chains and SimpleQA-class world knowledge; even after deploy, hard units must escalate.
- Flash Non-think without A/B is the same quality cliff as Pro Non-think on hard STEM.

---

## Evidence

| Claim | Source |
|-------|--------|
| Flash candidate; not deployed; needs swap or new endpoint | `05b-web-flash-vs-pro.md` |
| Flash decode / Pro decode central **1.7×**; think on/off >> tier | `05z-web-hosted-latency.md` |
| `SERVICES.toml` = Pro only on alliance-pod | `05b`; workspace `SERVICES.toml` |
| Reject ledger: Flash without new deploy | `SYNTHESIS.md`, `PLANNING-HANDOFF.md` §8 |
| CN: Flash can beat Pro on rule-literal JSON; still needs serve path | `05y-web-cn-forums.md` |

---

## Reopen conditions

Reopen only if **all** hold:

1. Flash endpoint returns 200 on `/v1/models` (or ops-approved Pro→Flash swap with documented Pro fallout).
2. Tapetum unit-check A/B: Flash High agreement with Pro High within fail-closed flip budget; retry rate not up.
3. Wall model uses measured alliance (or same-stack) Flash L, not Together peak tok/s; default prior remains **1.7×** until measured.
