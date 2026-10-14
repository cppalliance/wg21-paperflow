# Card 05k — Prefill/decode disaggregation on one 8×H200

**Source report:** `05k-web-pd-disagg.md`  
**Verdict in source:** **no** (waste for this fleet)

## Bottom line

P/D disagg is a real multi-node / long-OSL goodput tool. On one DeepSeek FP8 8×H200 running short-output decode-bound judges, it is the wrong topology and the wrong workload class. Prefer decode shrink, call elimination, APC/prefix, MTP A/B, dense offload.

## Numbers

- Our phase split: **~5.91 s decode vs ~0.46 s prefill** (~8% prefill); pass-path ~**55** tokens (shrinking).
- Anyscale: PD loses on short-output (classification/extraction); savings = TPOT_delta × OSL.
- Single-node MORI-IO 2.5×: Qwen3-235B, ISL=2000 / **OSL=1000**, 4P+4D — not portable to us.
- DeepSeek FP8: ~**805 GB**; needs full **8×H200** per replica; 4×H200 ≈564 GB cannot hold a second full replica.
- AWS multi-node lesson: disagg pays off mostly in **latency**, not tok/s/GPU; unified often best efficiency; knee ~1P:4D multi-node.
- Generous intuition: 10 ms/token × 55 tok ≈ **0.55 s/call** (~3% of ~20 s) — and topology unavailable without second node or quality-changing shrink.

## Architecture implication

Classic 4P+4D on one node is **not available** for DeepSeek-class FP8. Multi-node PD forbidden (no twin / no second V4-Pro). EP prefill-stall mechanism is real at scale but headroom is small vs decode shrink / N cuts here.

## Reject-or-A-B

**Reject** for this program. Reopen only if alliance-pod A/B shows ≥15% per-call wall drop on tapetum shapes under S=16/c=32 without a second node, or an official single-replica single-node PD recipe with short-OSL wins.

## Links

- https://www.anyscale.com/blog/ray-vllm-prefill-decode-disaggregation-amd-mi325x-67-percent-savings
- https://vllm.ai/blog/2026-04-07-moriio-kv-connector
- https://recipes.vllm.ai/deepseek-ai/DeepSeek-V3
- https://github.com/awslabs/awsome-distributed-ai/.../dsv3-uccl-nixl/README.md
- https://vllm.ai/blog/2025-12-17-large-scale-serving
