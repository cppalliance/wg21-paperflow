# CARD: Payload scope for dense S>16

## Bottom line (3 sentences max)
Minimal **presence-index + H2 window (±1)** in `_check_one_unit` caps unit LLM input at ~**10–12k tokens**, unlocking dense **S=32–48** with FP8 KV on `h200-qwen3-32b`. Without scoping, full-md p95 (~50k tok) keeps dense at **S≤16**, L≈20 s — offload is negative EV. Scoping is a dense enabler, not by itself a ≤600 s closer (MoE monolith queue still binds).

## Numbers that matter
- Candidate sizes today: P50 ~**8.5k** tok; P90 ~**35k**; P95 ~**50k**
- Scoped ~12k + FP8: ~**1.5 GiB/seq** → S **32–48**, L_unit hyp. **8–12 s** → T_dense **315–566 s** (1510 calls)
- Full md @ S=16: T_dense **~1888 s** (worse than keeping units on MoE)
- Prefill-only win @ MoE S=16: ~**198 s** (~7% of 3003 s)
- Oversize MoE fallback class: ~**8/381** papers

## Architecture implication
Scope **only** unit-check LLM prompts in v1; leave monolith/page/metadata and full-doc post-hoc grounding unchanged. Constants: soft 8192 / hard 12288 chars, neighbor ±1; hard overflow → MoE fallback (fail-closed). Land scoping + FP8 + bench before dense `_LANE_VERSION` bump; require 381/381 fused parity.

## Cite / do not re-open
- Dense S=48 without payload scoping or FP8 KV
- Silent truncate on dense instead of MoE fallback
- Claiming scoping alone hits ≤600 s on one MoE pod
- Scoping monolith/page escalation in the same v1 change set

## Links to related reports
- `research/cold-run-10min-1pod/23-payload-scope-dense.md` (this source)
- `12-dense-offload-architecture.md`, `20-heterogeneous-wall.md`, `19-quality-gate-1pod.md`
- Prior: `tapetum-llm-speedup/{13-payload-scoper,105-vllm-dense-judge-throughput}.md`
