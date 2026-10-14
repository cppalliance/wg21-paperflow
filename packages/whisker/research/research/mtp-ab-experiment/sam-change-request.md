# MTP A/B: Change-Request for Sam

**Date:** 2026-08-25  
**Context:** MTP k=1 A/B test on alliance-pod (ADR-014)  
**What:** Add speculative decoding (MTP) + CUDA graph decode to the pod start command  
**Revert:** Remove both flags, restart  

---

## Diff (against current H200SXM.txt)

The current container start command ends with:

```
--enable-log-requests --uvicorn-log-level info
```

**Append** these two flags (after `info`, before end):

```
--speculative-config '{"method":"mtp","num_speculative_tokens":1}' --compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'
```

### Full modified start command (copy-paste ready)

```
deepseek-ai/DeepSeek-V4-Pro --tensor-parallel-size 8 --enable-expert-parallel --enable-ep-weight-filter --max-model-len 393216 --max-num-seqs 16 --gpu-memory-utilization 0.95 --trust-remote-code --served-model-name deepseek-v4-pro --kv-cache-dtype fp8 --reasoning-parser deepseek_v4 --reasoning-config '{"reasoning_start_str":"<think>","reasoning_end_str":"</think>"}' --enable-auto-tool-choice --tool-call-parser deepseek_v4 --enable-log-requests --uvicorn-log-level info --speculative-config '{"method":"mtp","num_speculative_tokens":1}' --compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'
```

---

## What stays unchanged

- `--max-num-seqs 16`
- `--kv-cache-dtype fp8`
- `--max-model-len 393216`
- `--gpu-memory-utilization 0.95`
- TP8 + EP topology
- `--served-model-name deepseek-v4-pro` (no client changes needed)
- `--enable-prefix-caching` is NOT in the current template (prefix caching is on by default in vLLM 0.24.0)
- Container image `cppalliance/vllm-openai:v0.24.0` stays the same

---

## Verification after restart

Once the pod is back up:

1. `GET /version` must return `0.24.0`
2. `GET /v1/models` must show `deepseek-v4-pro`
3. `/metrics` must show new counters:
   - `vllm:spec_decode_num_draft_tokens_total`
   - `vllm:spec_decode_num_accepted_tokens_total`
4. Startup log should contain `SpeculativeConfig` and `compilation_config`

If counters are missing or the pod does not start: revert (see below).

---

## Revert (if test fails or pod does not start)

Remove the two appended flags:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":1}' --compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'
```

Restart the pod. The original start command is archived above and in:  
https://raw.githubusercontent.com/cppalliance/runpod/master/templates/deepseek/H200SXM.txt

---

## Why

- MTP head weights are already in the checkpoint (`num_nextn_predict_layers: 1`, 2343 tensors)
- k=1 only (ADR-014: k>=2 is anti-pattern for short JSON output)
- CUDA graphs (FULL_DECODE_ONLY) required by ADR-014 to prevent eager-mode argmax flips
- No other flags changed: isolates MTP contribution for the A/B measurement
- H200 MTP crash (#41483) was fixed in vLLM 0.20.2; we are on 0.24.0

---

## Result (2026-08-26): REVERT

A/B gate failed. Acceptance 92.3% (good). Wall 3315.6 s vs median baseline 3185.2 s (no win). JSON errors slightly worse. Please remove the two appended flags and restart. Details: RESULTS.md
