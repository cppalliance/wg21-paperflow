# CARD: 05o — LocalLLaMA V4-Pro self-host latency tips

## Bottom line
Community Pro tips that transfer to alliance-pod: under saturated batch, kill speculative decoding (DSpark/MTP overhead); keep full-GPU expert residency (no hybrid offload experiments); keep recipe hygiene (fp8 KV, block 256, FP4 indexer, CUDA graphs, EP-gated MegaMoE). Most LocalLLaMA Pro threads are hybrid CPU-expert rigs — take stack hygiene, ignore AVX/home-offload folklore.

## Numbers
- Single B300 batch job: disabling DSpark ~**2×** aggregate throughput at high `max_num_seqs`.
- Dual RTX PRO 6000 all-in-VRAM vLLM ~**72 tok/s** @ 250k vs hybrid GGUF ~**7–12 tok/s**.
- Best reported offline batch ~**770** agg out tok/s (B300, vLLM 0.25, reasoning on, `max_num_seqs=256`).
- Alliance-pod already at `max-num-seqs 16`, client c=32 (near slot saturation).

## Architecture implication
Reinforce keep DP+EP full-GPU recipe; do not invent partial-expert VRAM offload on the cold-run path. Speculative decode (MTP/DSpark) is measure-or-off for short JSON judges, not a default win. MegaMoE/`deep_gemm_mega_moe` requires expert parallel or it falls back slower.

## Reject-or-A-B
- **A/B:** MTP/DSpark **off** at fixed S=16 on short structured mix (aligns with `05a` short-OSL risk).
- **Reject:** hybrid MoE offload experiments as a ≤600 s lever; AVX rebuild as a latency path.
- **Keep (not A/B):** fp8 KV, CUDA graphs, FP4 indexer, EP on multi-GPU — recipe hygiene already pointed by official cards.

## Links
- Source: `05o-web-localllama.md`
- Related: `05a-web-deepseek-vllm.md` / `05a` MTP notes, `00-baseline.md`, `16-server-ops-1pod.md`
- https://www.reddit.com/r/LocalLLaMA/comments/1v2rtmk/ds_v4_on_single_b300_only_770_toks_batched_in_vllm/
- https://www.reddit.com/r/LocalLLaMA/comments/1tdpk3f/i_have_even_faster_deepseek_v4_pro_at_home/
- https://www.reddit.com/r/LocalLLaMA/comments/1t94ito/i_have_deepseek_v4_pro_at_home/
