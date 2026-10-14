# Card 05g — SLMJury / JudgeLM / Prometheus / PairRM

**Source report:** `05g-web-slmjury.md`  
**Verdict in source:** usable-with-conditions

## Bottom line

**3× unit decode does not require distillation.** Fastest honest path: off-shelf dense on live Alliance pod (`h200-qwen3-32b`) + payload scoping + SLMJury-style short pass-path tokens (Path F, days–1 week). ~1510 labels/run is below JudgeLM’s smallest scaling point (3.5K); SFT is Path S only if Path F fails quality. PairRM is the wrong tool shape for UnitCheck.

## Numbers

- SLMJury: Phi-4 14B **89.55%**, Qwen3-14B **89.51%**, Qwen3-8B **88.96%** @ B=10; open/general axes lose up to **~23%**.
- JudgeLM agreement: 7B@3.5K **75.9%**; 7B@100K **83.7%**; 33B@100K **~90%**. Public distill volumes 100K–300K for general judges.
- Our one cold run: ~**1510** UnitCheck teacher rows; production SFT floor ≥**5K** (ideal 8–12K).
- Ensembles: majority +0.06% once ~89% saturated; RCR debate degrades binary accuracy.
- Unit KPI: L 20→≈6.7 s @ S=48 → T_unit ≈ 1510×6.7/48 ≈ **211 s** (or ~93 s after metadata short-circuit). Fleet still `max(T_dense, T_moe)`; monolith ~500–710 s without MODERATE cuts.
- Path F pass: p50 decode ≤~2.0 s **or** ≥3× loaded-MoE tok/s (~40→≥120) **or** L_unit ≤~6.7 s at S≥32.

## Architecture implication

Path F: scope ~10–15k → route units to dense → Non-think + max_tokens 10–60 on pass path → bench. Keep monolith/oversize/escalate on alliance-pod. Path S (2–10 weeks): grow labels, LoRA 8–14B, MoE fallback. 3× unit decode is a **unit-leg KPI**, not a solo ≤600 s path.

## Reject-or-A-B

**Adopt Path F for lab 3×** (quality still UNVALIDATED until 381/381). **Reject:** twin V4-Pro; PairRM as unit judge; jury of 3 SLMs; waiting for 100K GPT-4 KD; dense without scoping. Cite 89.55% as fused-verdict proof = false-pass risk.

## Links

- https://arxiv.org/abs/2606.07810 (SLMJury)
- https://arxiv.org/abs/2310.17631 (JudgeLM)
- https://arxiv.org/abs/2310.08491 / https://arxiv.org/abs/2405.01535 (Prometheus)
- https://huggingface.co/llm-blender/PairRM
- `12-dense-offload-architecture.md`, `00-baseline.md`
