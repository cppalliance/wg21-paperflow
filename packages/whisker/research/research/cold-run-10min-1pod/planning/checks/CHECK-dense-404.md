# CHECK: All 4 dense pods return 404

**Claim:** All four dense offload pods answer HTTP 404 on liveness probe.
**Source:** `26-dense-pod-liveness.md`

## Quote

> **zero of four** dense offload pods answer `GET /v1/models` today (2026-07-24); all return HTTP **404** (empty body).
>
> Runtime probe … on all four dense services → **404** … on every endpoint.

## Verdict

**CONFIRMED** — report 26 marks all four DOWN with 404.
