# Card 05m — Short-OSL MoE scheduler flags (seqs=16)

**Source report:** `05m-web-short-osl-moe.md`  
**Verdict in source:** usable-with-conditions

## Bottom line

V1 already decode-prioritizes via chunked prefill. The win is **MBT / MTP / CUDA-graph decode path**, not disabling chunked prefill or flipping `--scheduling-policy`. Hold `--max-num-seqs 16`; raise MBT to **16384**.

## Numbers

- Recipe pin: `--max-num-seqs 16 --max-num-batched-tokens 16384`.
- Measured **16→32 = +57%** wall (slots-32 regression / baseline).
- V1: cannot disable chunked prefill (#18547); decode batched before prefill; remaining MBT fills with prefill chunks.
- Docs: MBT >8192 for throughput; smaller MBT (e.g. 2048) for ITL.
- MTP start `num_speculative_tokens: 1`; recipe `FULL_DECODE_ONLY` cudagraphs; k=2 hurts short OSL (prior ops checklist).
- Co-tune `--long-prefill-token-threshold 8192` with MBT 16384.
- Scheduler flags cut **L**, not S; combined ops envelope ~**300–550 s** (prior checklist), not a path to S=32.

## Architecture implication

Minimal delta: seqs=16, MBT=16384, long-prefill-threshold=8192, EP on, MTP k=1 A/B, FULL_DECODE_ONLY graphs. Leave `--scheduling-policy fcfs` unless client tags priority. `--async-scheduling` cheap A/B. DBO + `deepep_low_latency` only if DP>1 + DeepEP; skip on pure TP+EP. Anti: `--no-enable-chunked-prefill`, seqs=32, priority without tags, MTP k≥2 before acceptance metrics, `deepep_high_throughput` for this decode-heavy mix.

## Reject-or-A-B

**Adopt** MBT 16384 + graphs + hold seqs=16. **A/B** MTP k=1 and async-scheduling. **Reject:** disabling chunked prefill; raising seqs; banking k=2. Mind-changer: A/B showing MBT 8192 beats 16384 on this judge mix.

## Links

- https://docs.vllm.ai/en/stable/configuration/optimization/
- https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro
- https://github.com/vllm-project/vllm/issues/18547
- https://docs.vllm.ai/en/latest/features/speculative_decoding/mtp/
- https://docs.vllm.ai/en/stable/serving/expert_parallel_deployment/
- Prior: `research/cold-run-10min/26-server-ops-checklist.md`
