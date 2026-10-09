# ADR-005: Dense primary = Qwen3-32B (`h200-qwen3-32b`)

**Status:** Proposed

**Date:** 2026-07-24

---

## Context

ADR-003 routes ~82% of tapetum LLM calls (unit checks + metadata) off `alliance-pod` onto an existing dense endpoint. Candidate services in `SERVICES.toml`:

| Service | Model | Role considered |
|---------|-------|-----------------|
| `h200-qwen3-32b` | Qwen/Qwen3-32B | Primary |
| `b300-qwen36-27b` | Qwen/Qwen3.6-27B | Latency / quality pilot #2 |
| `b200x2-gemma4` | google/gemma-4-31B-it | Avoid as unit primary |
| `b200-r1` | deepseek-r1-distill-70b | Avoid |

Public judge literature and serving numbers favor a **Qwen3 dense 27–32B** class for structured unit verification vs large MoE teachers. No public study measures these three specifically against DeepSeek-V4-Pro on our UnitCheck schema — Alliance A/B remains mandatory.

As of 2026-07-24, all four dense pods return 404 on `/v1/models` (`26-dense-pod-liveness.md`). Model choice can be decided now; validation waits on restart (ADR-003 blocker).

---

## Decision

**Primary dense judge:** `h200-qwen3-32b` (Qwen3-32B).

**Reserve / pilot #2:** `b300-qwen36-27b` — only after 32B A/B passes, or as a parallel latency pilot if 32B holds quality and decode headroom is needed (hypothesis ≥2× decode, higher false-clear risk until proven).

**Do not use as unit primary:**

- `b200x2-gemma4` — constrained JSON / grammar collapse in public reports; prior false-fail hypothesis on `:::wording-remove` / `<del>` markup; only live dense with `tools_capable` (irrelevant for UnitCheck schema).
- `b200-r1` — 70B + thinking blocks; ≤1.5× decode hypothesis; no throughput persona support.

Class label: `qwen3-dense-27-32b` (not "any ~30B dense").

Dense vLLM recipe (delta from MoE): `--max-num-seqs 48`, `--kv-cache-dtype fp8`, `--enable-prefix-caching`, `--max-num-batched-tokens 16384`, after ADR-004 scoping. Target shapes: **12k/256** (and 8k/256) for bench.

---

## Consequences

**Positive**

- Best public judge-spine evidence in class (Nemotron-32B-Reward on Qwen3-32B ≈70B RM on JudgeBench; strong code-judge family).
- Schema / `vllm_thinking` path already mature in our stack.
- Faster decode and better concurrency than large MoE teachers on public benches — matches why offloading unit volume helps at MoE S=16.
- Aligns with deepest prior throughput modeling (`16`, `12`, `105`).

**Negative / constraints**

- Absolute agreement vs V4-Pro on WG21 unit defects is **unmeasured** until 381/381 A/B.
- SLMJury ~90% closed-ended oracle is **not** sufficient for ship (only 16/381 papers flip fused verdict).
- Pod must be restarted and recipe applied; wall claims (~511 s class) remain hypothetical until live bench + cold A/B.
- Bundling: do not ship dense service swap in the same `_LANE_VERSION` as metadata short-circuit or HMAC reorder without a bundled B run.

---

## Evidence

| Claim | Source |
|-------|--------|
| Rank 1 = Qwen3-32B; rank 2 = Qwen3.6-27B; avoid Gemma-4 primary | `05f-web-dense-judge-lit.md` |
| Nemotron-32B-Reward JudgeBench ~72.3 vs 70B ~73.7; code 83.3 | HF nvidia/Qwen-3-Nemotron-32B-Reward via `05f` |
| Judge's Verdict: ~30B-class can be Tier 1 vs humans (sibling/caveat) | arXiv:2510.09738 via `05f` |
| Gemma-4 JSON/schema collapse | Ollama #15502, gemma#622 via `05f` |
| Architecture primary assignment `h200-qwen3-32b` | `12-dense-offload-architecture.md` |
| Cascade design uses same primary | `05l-web-cascade-papers.md` |
| Dense pods down (404); alliance-pod up | `26-dense-pod-liveness.md` |
| Quality gates: 381/381 + equivalence vector + `_LANE_VERSION` | `12`; `25-quality-gate-protocol.md` |

---

## Open blockers

1. **Restart `h200-qwen3-32b`** (minimum for pilot); confirm `/v1/models` 200 + unit-check smoke (`26`).
2. **ADR-004 payload scoping landed** before claiming S=32–48 / 2× decode.
3. **`vllm bench serve`** Qwen3-32B vs `alliance-pod` at 12k/256 and 40k/900; abort speed claim if measured `L_dense ≥ L_moe`.
4. **381/381 fused-verdict parity A/B** (suggested_verdict, fusion.combined_verdict, defect-group multiset, coverage tuple); audit 1057/1510 zero-defect disagreements; holdout wording papers.
5. **MoE fallback for 8/381 oversize** papers — no truncate-and-run on dense.
6. Optional after pass: promote or bench `b300-qwen36-27b`; reopen Gemma only if ≥99% valid JSON on our vLLM + schema and full parity.
