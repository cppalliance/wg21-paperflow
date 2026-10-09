# 26 - Dense Pod Liveness

**Verdict:** blocked — **zero of four** dense offload pods answer `GET /v1/models` today (2026-07-24); all return HTTP **404** (empty body). Dense unit/metadata offload in `12-dense-offload-architecture.md` is **infra-blocked** until at least one pod is restarted.
**Confidence:** high

**Date:** 2026-07-24. Sources: runtime probe (this session), `SERVICES.toml:76-138`, `research/cold-run-10min-1pod/12-dense-offload-architecture.md`, `research/cold-run-10min/16-dense-judge-candidates.md`.

---

## Findings

- [CRITICAL] **No dense pod is live today.** Runtime probe: `GET {base_url}/v1/models` with configured credential, **12 s timeout**, on all four dense services → **404** (empty body, `Content-Length: 0`) on every endpoint. Same 404 on `/health` and `/` for `h200-qwen3-32b` (RunPod proxy up, pod instance not serving). Impact: **~1879 calls (82.3%)** that `12-dense-offload-architecture.md` routes to `h200-qwen3-32b` cannot run on dense today; cold fleet must stay on `alliance-pod` MoE only.

- [CRITICAL] **Probe method validated against live control.** `alliance-pod` (`sgjy18glyi4blu-8000.proxy.runpod.net`) → **200**, body lists `id: deepseek-v4-pro`, `max_model_len: 393216` (~370 ms). Confirms 404 on dense pods means **pod down**, not probe misconfiguration.

- [HIGH] **Prior doc assumed liveness without same-day probe.** `16-dense-judge-candidates.md` (same date) lists four services as "live open-weight pods" from `SERVICES.toml` inventory only. Today's probe contradicts that assumption. Impact: dense-judge throughput personas (`105-vllm-dense-judge-throughput.md`) and offload wall estimates (~510–710 s) are **hypothetical until pods revive**.

- [MED] **All four dense services use literal keys in TOML.** No env-var indirection (unlike `alliance-pod` → `$ALLIANCE_POD_KEY`). Keys redacted below as `sk-{pod-id-prefix}***`. Impact: health checks need no `.env`; credentials are committed pod-id prefixes in `SERVICES.toml`.

- [LOW] **404 signature matches dead twin MoE pod.** Same pattern as `h200x8-deepseek-v4-pro` in `15-dual-pod-liveness.md`: fast empty 404 via Cloudflare/RunPod proxy (~250–825 ms). No chat/completions sent; probe is read-only.

---

## Alive today (2026-07-24)

| Service | Status | Model (configured) | Notes |
|---------|--------|-------------------|-------|
| `h200-qwen3-32b` | **DOWN** | `Qwen/Qwen3-32B` | 404 all paths |
| `b200x2-gemma4` | **DOWN** | `google/gemma-4-31B-it` | 404 |
| `b300-qwen36-27b` | **DOWN** | `Qwen/Qwen3.6-27B` | 404 |
| `b200-r1` | **DOWN** | `deepseek-r1-distill-70b` | 404 |

**Dense pods alive: 0 / 4.**

For contrast (not in dense probe scope): `alliance-pod` MoE lane is **UP** (200, `deepseek-v4-pro`).

---

## Probe log (2026-07-24, credentials redacted)

| Service | Base URL | Auth source | HTTP | Elapsed | Body |
|---------|----------|-------------|------|---------|------|
| `h200-qwen3-32b` | `https://d5htj97igzetl6-8000.proxy.runpod.net` | TOML literal `sk-d5ht***` | **404** | ~365–825 ms | empty |
| `b200x2-gemma4` | `https://auzznfc1ourtrk-8000.proxy.runpod.net` | TOML literal `sk-auzz***` | **404** | ~262–316 ms | empty |
| `b300-qwen36-27b` | `https://5c9q67uhzngqc5-8000.proxy.runpod.net` | TOML literal `sk-5c9q***` | **404** | ~253–319 ms | empty |
| `b200-r1` | `https://hdsfzi29n4xyup-8000.proxy.runpod.net` | TOML literal `sk-hdsf***` | **404** | ~251–349 ms | empty |
| `alliance-pod` (control) | `https://sgjy18glyi4blu-8000.proxy.runpod.net` | `$ALLIANCE_POD_KEY` from `.env` | **200** | ~370 ms | `deepseek-v4-pro`, max len 393216 |

**Method:** `GET /v1/models`, `Authorization: Bearer {key}`, `--max-time 12`. Keys never logged in full.

**TOML refs:** `SERVICES.toml:76-85` (`b200-r1`), `:87-97` (`b200x2-gemma4`), `:99-108` (`b300-qwen36-27b`), `:129-138` (`h200-qwen3-32b`).

---

## What would change my mind

Any dense service returns **200** on `/v1/models` with its configured `model` id in the response body, plus a single unit-check smoke call completing without connection error. Minimum for offload pilot: **`h200-qwen3-32b` UP** (primary dense lane in `12-dense-offload-architecture.md`).

---

## False-pass hypothesis

Operator reads `16-dense-judge-candidates.md` ("four live dense pods") and schedules dense offload without probing. Fleet runs entirely on `alliance-pod`; wall stays MoE-bound (~11–14 min post-v11). No obvious error because MoE lane is healthy.

## False-fail hypothesis

If dense routing were wired without pre-gather health filter, ~82% of tapetum calls would hit dead proxies → mass `error` tombstones. Today: dense routing not shipped; failure mode is latent only.
