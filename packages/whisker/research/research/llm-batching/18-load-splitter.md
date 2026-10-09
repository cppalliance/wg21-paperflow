# 18 - Load-Splitter

**Verdict:** usable-with-conditions — dual-pod load split is architecturally free (existing `--service` overrides, no pipeline/paperstore edits), but the twin `h200x8-deepseek-v4-pro` endpoint returned HTTP 404 on every probed path today, so a 2× wall-time cut is **not** available until that instance is restarted; `alliance-pod` is live.
**Confidence:** high

## Findings

- [CRITICAL] The two pods are **distinct RunPod instances**, not aliases: `alliance-pod` → `https://sgjy18glyi4blu-8000.proxy.runpod.net/v1`, `h200x8-deepseek-v4-pro` → `https://w80putgan2qou8-8000.proxy.runpod.net/v1` (`SERVICES.toml:47-74`). Same model (`deepseek-v4-pro`), different proxy subdomains. Evidence: runtime probe 2026-07-07 — `alliance-pod` `/v1/models` → 200 (1 model); `h200x8-deepseek-v4-pro` `/v1/models`, `/v1/chat/completions`, `/health`, `/version` → 404 (empty body). Impact: code/config assume a second lane exists; **today only one lane is reachable**, so any 2× projection is blocked on infra, not whisker.

- [HIGH] **Zero-code split today** (when twin is live): two parallel CLI processes with **disjoint PID lists** and per-process `--service` overrides. Process A (default): `uv run whisker-tapetum-llm --concurrency 3 --review-all` or explicit PIDs (uses `tapetum_llm.md` defaults: all slots → `alliance-pod`). Process B: `uv run whisker-tapetum-llm --concurrency 3 --service fast=h200x8-deepseek-v4-pro --service deep=h200x8-deepseek-v4-pro --service default=h200x8-deepseek-v4-pro <other-half-pids>`. Evidence: `cli.py:150-156,365,429-435`; `adjudicate.py:444-446`. Impact: `T ≈ ceil(100/3)×30 s ≈ 17 min` per half → ~18 min wall (vs 36 min baseline) when both pods absorb c=3 independently.

- [HIGH] `--service` overrides are **per-run, not per-paper**: one `overrides` dict parsed at startup (`cli.py:365`) and passed unchanged into every `adjudicate_paper(..., service_overrides=overrides)` inside the gather loop (`cli.py:429-435`). Evidence: `adjudicate.py:425-446` rebuilds agents from the same merged map per paper. Impact: single-process round-robin requires a whisker-local change; cannot shard inside one run without it.

- [HIGH] **Minimal whisker round-robin** (~15 lines in `cli.py` only): add e.g. `--shard-pods NAME[,NAME,...]`; in `_adjudicate_one(index, pid)` compute `pod = shard_pods[index % len(shard_pods)]` and `per_paper = {**overrides, "fast": pod, "deep": pod}` (optionally `"default": pod` if overrides do not already repoint default). Pass `per_paper` to `adjudicate_paper`. Keep `asyncio.gather` + semaphore. Raise `--concurrency` to `2×` per-pod target (e.g. 6 for ~3 in-flight per pod) so round-robin does not serialize on one host when N=3. Impact: one process, one progress bar, ~2× throughput when both pods live.

- [MED] **Escalation / deep-slot caveat:** 13/197 papers fire tier-2 (`00-baseline.md:23-24`). `tapetum_llm.md:17-18` maps both `fast` and `deep` to the same service today. When sharding, **bind `fast` and `deep` to the same pod per paper** so tier-2 re-read stays colocated with tier-1 (prefix-cache locality, correct load accounting). Splitting only `fast` while `deep` stays on `alliance-pod` is safe but piles ~13 escalations onto pod A — negligible vs 200 tier-1 calls. Never leave `deep` unset on a shard that uses a different `fast` pod without intent. Impact: wrong split (fast on B, deep on A) does not break fidelity; it skews load and forfeits cache benefit.

- [MED] **Credential resolution:** `alliance-pod` uses `api_key = "$ALLIANCE_POD_KEY"` (`SERVICES.toml:67`); `ALLIANCE_POD_KEY` is **present** in gitignored `.env` (name only, value not logged). `h200x8-deepseek-v4-pro` uses a **literal** `api_key` in `SERVICES.toml:50` — no env var, so `resolve_pipeline_models` skips env validation for that entry (`services.py:501-513`). `load_services` never checks env presence (`services.py:119-120,19-26`); missing `ALLIANCE_POD_KEY` fails at **first** `adjudicate_paper` via `resolve_pipeline_models`, not at import. Impact: half-split on h200x8 only still requires `ALLIANCE_POD_KEY` unless `--service default=h200x8-deepseek-v4-pro` removes the `alliance-pod` binding from the effective map.

- [LOW] **`[defaults]` slot map does not exist** in `SERVICES.toml` (grep: no `[defaults]` section). LLM slot bindings for tapetum live in `tapetum_llm.md:15-19` (`fast` / `deep` / `default` → `alliance-pod`). `SERVICES.toml:13-16` documents that pipelines own slot maps, not the infra file. Impact: load-split docs must reference `tapetum_llm.md` + `--service`, not a nonexistent `[defaults]` block.

## False-pass hypothesis

Twin-pod sharding assigns papers to independent vLLM batch schedulers with no shared prefix-cache state. A PRIMARY false-pass candidate adjudicated on pod B may get a tier-1 `pass` with high confidence while the same paper on pod A (rerun) would have fired `axis_conflict` or `ungrounded_evidence` under a different MoE routing / batch composition (`16-determinism-auditor.md`). Whisker gate stays green; advisory distribution shifts by **which pod drew the paper**, not by conversion quality — looks like a successful speedup, masks run-to-run verdict drift across shards.

## False-fail hypothesis

If `h200x8-deepseek-v4-pro` is partially up (proxy routes but vLLM not ready), round-robin assigns ~half of papers to a failing endpoint. Batch firewall catches per-paper errors (`cli.py:451-462`) → inflated `error` count and `review` gaps in fusion, not spurious `fail` verdicts. Operators may interpret elevated errors as conversion problems when the root cause is a dead shard — a **throughput false-fail** (run looks broken) without semantic false-fails on good papers.

## What would change my mind

A live probe matching alliance-pod: `GET https://w80putgan2qou8-8000.proxy.runpod.net/v1/models` with the configured credential returns **200** and lists `deepseek-v4-pro`, followed by a 20-paper A/B wall-time test (10+10 disjoint PIDs, c=3 each process) showing combined elapsed ≤ 1.3× the slower single-pod half (allowing overhead). That would flip verdict to **usable** and quantify the free 2×; sustained 404 keeps the twin in the "false assumption" bucket.
