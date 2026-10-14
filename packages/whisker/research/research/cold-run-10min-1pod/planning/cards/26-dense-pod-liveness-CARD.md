# CARD: Dense pod liveness (2026-07-24 probe)

## Bottom line (3 sentences max)
**Zero of four** dense offload pods answer `GET /v1/models` today — all return HTTP **404** (empty body). Only control `alliance-pod` is **UP** (200, `deepseek-v4-pro`). Heterogeneous dense offload (`12`) is **infra-blocked** until at least `h200-qwen3-32b` is restarted.

## Numbers that matter
- Dense alive: **0 / 4** (`h200-qwen3-32b`, `b200x2-gemma4`, `b300-qwen36-27b`, `b200-r1`)
- Probe: `/v1/models` + Bearer, **12 s** timeout; dense **404** in ~250–825 ms; alliance-pod **200** ~370 ms
- Offload share blocked: ~**1879 calls (82.3%)** that would route to dense
- Prior “live pods” inventory (SERVICES.toml only) contradicted by same-day probe
- Minimum to unblock pilot: **`h200-qwen3-32b` UP** + one unit-check smoke

## Architecture implication
Do not schedule dense routing or bank ~510–710 s heterogeneous walls until ops restarts dense. Until then cold fleet stays MoE-only (~11–14 min post-v11 class). Wire pre-gather health probes before any dense router lands (avoid 404 storm if routing ships while pods down).

## Cite / do not re-open
- Assuming dense pods are live from TOML inventory without a same-day probe
- Planning Package C / ≤10 min as executable while all dense 404
- Treating proxy 404 as auth misconfiguration (control probe validates method)

## Links to related reports
- `research/cold-run-10min-1pod/26-dense-pod-liveness.md` (this source)
- `12-dense-offload-architecture.md`, `00-baseline.md`, `SYNTHESIS.md`, `PLANNING-HANDOFF.md`
- Prior: `cold-run-10min/16-dense-judge-candidates.md`, `SERVICES.toml:76-138`
