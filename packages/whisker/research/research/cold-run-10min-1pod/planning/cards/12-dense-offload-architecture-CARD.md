# CARD: Dense offload architecture (single MoE pod)

## Bottom line (3 sentences max)
Route ~**1879/2284 (~82%)** calls to `h200-qwen3-32b`, keep ~**428** on `alliance-pod`; fleet wall = **`max(T_dense, T_moe)`**. With payload scoping and 2× unit decode, central wall is **~511 s** (MoE-bound; range **~510–710 s** if metadata stays on MoE at 20 s). Quality-blocked until 381/381 A/B parity; without scoping, offload is **negative EV**.

## Numbers that matter
- Dense: ~**1502** in-budget units + **377** metadata; MoE: 381 first-pass + ~16 esc + 8 oversize + ~23 tier-2
- Dense S=**32–48** independent; MoE S=**16** fixed; per-pod semaphores (16 MoE / 32–48 dense)
- Scenario A (scoped, 2×): T_dense ~**352 s**, T_moe ~**511 s** → wall ~**511 s**
- Without scoping: dense L≈20, S≤16 → T_dense ~**2349 s** (`NEGATIVE-EV-WITHOUT-SCOPE`)
- Reserve: `b300-qwen36-27b` after A/B; avoid Gemma/R1 as primary unit lane

## Architecture implication
Land payload scoping (~10–15k tokens) **before** dense `_LANE_VERSION` bump. Service router maps call class → MoE vs dense; oversize preflight mandatory. Hard ship gates: 381 fused-verdict parity, equivalence vector, MoE fallback for 8 papers, A/A noise floor, dev-replay, 48-anchor holdout. Do not bundle with short-circuit/HMAC in same lane bump without attribution plan.

## Cite / do not re-open
- Equating dense offload with “second V4-Pro pod”
- Enabling dense routing before payload scoping
- Using Gemma/`b200-r1` as default unit judge
- Claiming ≤600 s as reliable without MODERATE cuts + quality pass (fragile central only)

## Links to related reports
- `research/cold-run-10min-1pod/12-dense-offload-architecture.md` (this source)
- `00-baseline.md`, `20-heterogeneous-wall.md`, `19-quality-gate-1pod.md`, `23-payload-scope-dense.md`
- Prior: `cold-run-10min/16-dense-judge-candidates.md`, `tapetum-llm-speedup/{23-small-judge-evaluator,105-vllm-dense-judge-throughput}.md`
