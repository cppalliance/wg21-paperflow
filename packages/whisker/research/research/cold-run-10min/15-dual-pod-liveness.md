# 15 - Dual-Pod Liveness

**Verdict:** usable-with-conditions — `alliance-pod` is live and serving `deepseek-v4-pro` today, but twin `h200x8-deepseek-v4-pro` returns HTTP 404 on every probed path, so dual-shard ~1.9× wall savings are **not** available until that RunPod instance is restarted; no in-repo `--shard-pods` CLI exists yet.
**Confidence:** high

## Findings

- [CRITICAL] **Twin pod `h200x8-deepseek-v4-pro` is down today (2026-07-24).** Runtime probe: `GET https://w80putgan2qou8-8000.proxy.runpod.net/v1/models` with configured credential → **404** (empty body); same for `/health`, `/version`, `/`. Evidence: `SERVICES.toml:47-57` (`base_url`, literal `api_key` redacted as `sk-w80***`); prior probe 2026-07-07 matched (`packages/whisker/research/llm-batching/18-load-splitter.md:8`). Impact: dual-pod lever #4 in `00-baseline.md:35` blocked on infra; cold wall stays single-lane (~3003 s baseline) regardless of client levers.

- [CRITICAL] **`alliance-pod` is live and model-ready.** Runtime probe: `GET https://sgjy18glyi4blu-8000.proxy.runpod.net/v1/models` with `ALLIANCE_POD_KEY` (from gitignored `.env`, value not logged) → **200**, body lists `id: deepseek-v4-pro`, `max_model_len: 393216`. Evidence: `SERVICES.toml:64-74`; response length 478 B. Impact: all tapetum fleet traffic can run on this lane today; no second decode slot pool.

- [HIGH] **Dual-shard is NOT available today.** Both pods must answer `/v1/models` (or `/health`) 200 for the ~1.9× projection in `21-dual-pod-sharder.md:8` and `11-wall-arithmetic.md`. With twin 404: effective slots remain **16** (one pod), not 32. Workaround without code: two manual CLI processes with disjoint PID lists and `--service fast=h200x8-deepseek-v4-pro ...` on process B (`18-load-splitter.md:10`) — **blocked** while twin is dead.

- [HIGH] **No `--shard-pods` / dual-pod CLI implementation at HEAD.** Grep `packages/whisker/**/*.py` for `shard`, `shard-pods`, `shard_pods`, `dual-pod`: **zero matches**. `--service` overrides are per-run, not per-paper (`cli.py:327-331,383-389,1048,1410`; `10-impl-status-auditor.md:14`). Proposed fix: ~15–25 lines in `cli.py` only (`18-load-splitter.md:14`, `21-dual-pod-sharder.md:8-10`). Impact: even when twin returns, operators must split PIDs manually or ship shard flag first.

- [MED] **Credential layout differs by pod.** `h200x8-deepseek-v4-pro`: literal key in `SERVICES.toml:50` (`sk-w80***`, no env). `alliance-pod`: `api_key = "$ALLIANCE_POD_KEY"` (`SERVICES.toml:67`); key present in `.env` today (probe succeeded). Impact: twin health check needs no env; alliance probe requires `ALLIANCE_POD_KEY`; half-split on h200 only still needs alliance key unless all slots repointed.

- [MED] **Same model, distinct RunPod proxies — not aliases.** `alliance-pod` → `sgjy18glyi4blu-8000.proxy.runpod.net`; twin → `w80putgan2qou8-8000.proxy.runpod.net`; both `model = "deepseek-v4-pro"` (`SERVICES.toml:51,68`). Impact: when twin revives, sharding adds independent vLLM schedulers (verdict-drift caveat in `18-load-splitter.md:23-24`); not a config typo.

- [LOW] **Safe probe method confirmed.** `GET /v1/models` with 15 s timeout does not invoke completions or burn GPU decode. Twin/alliance probes completed in ~34–44 s wall (network + proxy latency). No chat/completions calls sent.

## False-pass hypothesis

Operator sees `alliance-pod` 200 and assumes `SERVICES.toml` declares two lanes, so schedules a cold fleet expecting ~1600 s wall. Twin 404 means only one pod absorbs 32 client workers — wall stays ~3003 s (or post-v11 ~11–14 min). Run "succeeds" with green gate; speed target missed without obvious infra error because health gate today probes only the effective `fast` slot once (`21-dual-pod-sharder.md:12`).

## False-fail hypothesis

If `--shard-pods` were implemented without pre-gather health filtering (`21-dual-pod-sharder.md:12-13`), round-robin would assign ~50% of papers to the dead twin → inflated `error` tombstones (`cli.py` batch firewall), operators misread as conversion breakage. Today: no shard flag, so this failure mode is latent only.

## What would change my mind

`GET https://w80putgan2qou8-8000.proxy.runpod.net/v1/models` returns **200** with `deepseek-v4-pro` in the model list, plus either (a) shipped `--shard-pods alliance-pod,h200x8-deepseek-v4-pro` with dual health probe, or (b) a 20-PID A/B (10+10 disjoint, c=3 each process) showing combined wall ≤ 1.3× the slower half. That would flip dual-shard to **usable** and unlock ~1.9× on the cold-run 10 min path.

## Probe log (2026-07-24, redacted)

| Endpoint | URL (base) | HTTP | Notes |
|----------|------------|------|-------|
| Twin `h200x8-deepseek-v4-pro` | `https://w80putgan2qou8-8000.proxy.runpod.net` | **404** | `/v1/models`, `/health`, `/version`, `/` |
| `alliance-pod` | `https://sgjy18glyi4blu-8000.proxy.runpod.net` | **200** | `/v1/models` → `deepseek-v4-pro`, max len 393216 |

Credentials: twin uses committed literal key (`sk-w80***`); alliance uses `$ALLIANCE_POD_KEY` from `.env` (not printed).
