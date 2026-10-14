# ADR-030: Fail closed when dense is selected but down

## Status

Proposed — hard invariant before Option B ship

## Date

2026-07-24

## Context

Option B routes ~**1879** calls (~82% of fleet) to `h200-qwen3-32b`. As of the 2026-07-24 probe, **all four** dense `SERVICES.toml` endpoints return HTTP **404** on `/v1/models`; only `alliance-pod` is up (`26`).

Two failure modes if dense routing ships without discipline:

1. **Mass errors:** ~82% of calls hit dead proxies → error tombstones / fleet fail.
2. **Silent MoE fallback:** client detects 404/5xx and dumps the entire unit+metadata queue onto `alliance-pod` without declaring that heterogeneous offload is offline. Wall reverts to MoE-bound (~15–25 min class) while operators still believe “dense offload is live” and may still quote ≤10 min.

ADR-029’s oversize→MoE path is a **small, expected** cohort (~8). Pod-down fallback of the full dense queue is a **different event** and must not be silent. ADR-018 already forks the SLA if dense stays down.

## Decision

1. **Pre-gather health gate.** Before enabling dense routing for a fleet run: `GET /v1/models` must return **200** with the configured model id, plus a unit-check smoke completion. If the gate fails, **do not** enter dense routing mode.
2. **If dense is selected in config but health fails (404 / connection / smoke fail):**
   - **Fail closed** on the heterogeneous claim: refuse to label the run as Config B / offload-enabled.
   - Either abort with a clear error, or continue **explicitly as MoE-only** with a loud SLA note in logs, trace, and operator summary: offload inactive; expect Option A / ~15–20 min class walls; ≤10 min **not** claimed.
3. **Forbidden:** silent redirect of the full dense call set to `alliance-pod` while leaving dense service selection marked enabled / success.
4. MoE fallback remains allowed **only** for the ADR-029 oversize / scope-fail cohort (and calibrated unit escalate ≤15%), not as a substitute for a dead dense pod.
5. Mid-run dense death after a passed pre-gather: surface errors; do not invent a quiet full-queue MoE drain without the same SLA note.

## Consequences

**Positive**

- Prevents false “offload live” reads when wall is MoE-only.
- Aligns runtime behavior with ADR-018 SLA fork and `26` false-pass hypothesis.
- Avoids mass tombstones from wiring dead endpoints without a health filter (`RISK-REGISTER.md`).

**Negative / cost**

- Requires a health probe and explicit degraded-mode messaging in CLI/ops.
- Cannot “soft launch” dense config against 404 endpoints hoping MoE catches everything.

## Evidence

| Claim | Source |
|-------|--------|
| 0/4 dense UP; 404; alliance-pod 200 | `26-dense-pod-liveness.md` |
| ~1879 calls routed to dense in architecture | `12-dense-offload-architecture.md` |
| Dead dense without health filter → tombstones; MoE fallback only for oversize-8 | `RISK-REGISTER.md` |
| False-pass: fleet stays MoE, no obvious error | `26-dense-pod-liveness.md` |
| SLA fork if dense stays down | ADR-018, `PLANNING-HANDOFF.md` §4, `SYNTHESIS.md` |
| Ship Option B or fail closed | `PLANNING-HANDOFF.md` §6 P7 |
