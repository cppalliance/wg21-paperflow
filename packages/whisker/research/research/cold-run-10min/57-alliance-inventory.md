# 57 - Alliance Endpoint Inventory (dual-shard + dense offload)

**Date:** 2026-07-24  
**Sources:** `alliance_models.json`, `SERVICES.toml` (active `[services.*]` only). Secrets redacted: no `base_url`, no API keys.

**Verdict:** `alliance-pod` is confirmed live for `deepseek-v4-pro`. Dual-shard needs a second identical twin; dense offload has four declared dense pods (27B–70B). Twin health for `h200x8-deepseek-v4-pro` is not confirmed by `alliance_models.json` (alliance-scoped probe only).

---

## Dual-shard (same-model MoE twins)

Requires **identical** `model` on two `vllm_thinking` services. Assignment: `index % len(live_pods)` after health probe (`21-dual-pod-sharder.md`).

| Service name | Model |
|--------------|-------|
| `alliance-pod` | `deepseek-v4-pro` |
| `h200x8-deepseek-v4-pro` | `deepseek-v4-pro` |

**Today:** `alliance_models.json` lists one model on the alliance probe:

| Model id | max_model_len |
|----------|---------------|
| `deepseek-v4-pro` | 393216 |

That matches `alliance-pod` / `h200x8-deepseek-v4-pro` entries in `SERVICES.toml`. Prior cold-run notes: twin may return 404 while `alliance-pod` is healthy; single-pod fallback is expected (`22-path-a-b-10min.md`, `21-dual-pod-sharder.md`).

---

## Dense offload (unit + metadata/outline judge lane)

Target: ~1887/2284 tapetum LLM calls off MoE (`16-dense-judge-candidates.md`). Backend: `vllm_thinking`. Monolith, escalations, and oversize payloads stay on MoE (393216 context).

| Service name | Model | Notes |
|--------------|-------|-------|
| `h200-qwen3-32b` | `Qwen/Qwen3-32B` | Primary AGGRESSIVE anchor |
| `b200x2-gemma4` | `google/gemma-4-31B-it` | Only live dense with `tools_capable` |
| `b300-qwen36-27b` | `Qwen/Qwen3.6-27B` | Smallest live dense |
| `b200-r1` | `deepseek-r1-distill-70B` | 70B dense; slower hypothesis |

All four: `max_context_window = 131072`, `thinking_capable = true`.

---

## Declared but not useful for these levers

| Service name | Model | Reason |
|--------------|-------|--------|
| `b300-qwen3-235b` | `Qwen/Qwen3-235B-A22B-FP8` | MoE (~22B active), not dense offload class |
| `anthropic-opus` | `claude-opus-4-6` | Cloud, not self-hosted open-weight |
| `# b200-qwen35` | `Qwen/Qwen3.5-122B-A10B-FP8` | Commented out, not live |
| `# b200-llama` | `llama-3.3-70b` | Commented out, not live |
| `# fireworks-405b` | `accounts/fireworks/models/llama-v3p1-405b-instruct` | Commented out, not live |

**Gap:** no live 7B–14B dense pod in `SERVICES.toml` (`16-dense-judge-candidates.md`).

---

## Summary counts (SERVICES.toml active LLM services)

| Role | Count | Service names |
|------|-------|---------------|
| Dual-shard twins | 2 | `alliance-pod`, `h200x8-deepseek-v4-pro` |
| Dense offload | 4 | `h200-qwen3-32b`, `b200x2-gemma4`, `b300-qwen36-27b`, `b200-r1` |
| Other MoE / cloud | 2 | `b300-qwen3-235b`, `anthropic-opus` |

**Pre-gather requirement:** probe each candidate with health or `/v1/models` before cold run; run only on `live_pods` (`21-dual-pod-sharder.md`).
