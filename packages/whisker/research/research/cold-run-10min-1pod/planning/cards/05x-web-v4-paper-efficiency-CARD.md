# CARD: 05x — V4 paper inference efficiency vs V3.2

## Bottom line
Paper headline at 1M ctx: V4-Pro ≈ **27% FLOPs / 10% KV** vs V3.2 (Flash ≈ **10% / 7%**) via hybrid CSA+HCA, FP8 KV, FP4 indexer/experts. Core architecture is already paid by serving V4-Pro. Unused headroom is product dials + serving recipe (Non-think, Flash, MTP, APC, DeepEP), not a missing “turn on CSA” switch.

## Numbers
- Pro: 49B activate, **0.27×** FLOPs / **0.10×** KV vs V3.2 @ 1M (~**3.7×** / ~**10×**).
- Flash: 13B activate, **0.10×** / **0.07×**.
- CSA compress ~**4×**; HCA ~**128×**; MegaMoE claims **1.50–1.73×** vs non-fused EP (up to ~1.96× latency-sensitive).
- Gains “especially in long-context”; 1M figure is wrong denominator for ~20 s thinking-decode wall.
- Vs BF16 GQA-8: V4 KV @ 1M ~**2%** (different baseline — do not mix with V3.2 ratios).

## Architecture implication
Do not plug paper FLOPs ratios into `wall = (N×L)/16`. Prefill/KV wins already justify Pro at 393k / S=16. Close remaining gap with N cuts + decode shrink + dense offload + ops recipe. Confirm image loads V4 kernels + fp8 KV; MTP/DeepEP/APC/Non-think remain real dials.

## Reject-or-A-B
- **Reject false claim:** “fleet isn’t using V4 architecture” / rediscovering CSA as a cold-run lever.
- **A/B (product dials):** Pro Non-think or Flash for unit/metadata with quality gate (see `05b`, `05q`).
- **Ops A/B:** MTP k=1, DeepEP-LL+DBO, APC retention — paper-adjacent, wall-relevant.
- **False-fail to avoid:** “already on Pro so paper is irrelevant” (MTP/DeepEP/Non-think/Flash still unused).

## Links
- Source: `05x-web-v4-paper-efficiency.md`
- Related: `05b-web-flash-vs-pro.md`, `16-server-ops-1pod.md`, `59-deepseek-v4-release.md`
- https://arxiv.org/html/2606.19348
- https://huggingface.co/blog/deepseekv4
