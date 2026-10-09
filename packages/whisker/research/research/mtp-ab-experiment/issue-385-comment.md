Related measurement (different stack). This does not close the Qwen3.8-27B Q4 local llama.cpp A/B, and it does not replace the 9B proxy table already on this issue.

We ran MTP on the live alliance-pod: DeepSeek-V4-Pro (Preview), vLLM 0.24.0, 8x H200, TP8+EP, `--max-num-seqs 16`. Client was `whisker-tapetum-llm`, not a local llama.cpp bench.

## Conclusion

MTP k=1 does not help this fleet. Draft acceptance is healthy (92.3%). Output quality stays inside run-to-run noise. Wall time does not improve. Stop here. Do not try k=2 or k=4 on this pod. Revert the two flags.

High acceptance is not a wall win. This workload is short structured JSON at a packed batch (S=16, client c=32). That is the published lose/flat zone for MTP, not a broken drafter.

## What we actually ran (not a full corpus run)

This was **not** `whisker --all` and **not** a bare `whisker-tapetum-llm` full converted-paper run.

Command (same on every arm):

```
uv run whisker-tapetum-llm --review-all --force --concurrency 32 --trace
```

`--review-all` selects risk candidates from existing whisker sidecars (`select_candidates`). This machine resolved **367 PIDs**. Incremental skip is off by default on `--review-all`, so each arm re-evaluated those 367 papers. `--force` is ignored on that flag.

| Step | MTP | What |
|---|---|---|
| A1 | off (N=0) | 367 papers, back-to-back baseline |
| A2 | off (N=0) | same 367 papers, AA noise floor |
| Sam restart | k=1 | `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` plus `--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'` |
| Smoke | k=1 | P4182R0, P4185R0, `--debug` |
| B1 | k=1 (N=1, not N=2) | same 367 papers |

Sidecars snapshotted after each arm. `/metrics` scraped before/after (prompt, gen, prefix cache, `spec_decode_*`).

## Wall and tokens (publish the raw deltas)

CLI footer wall, same 367 papers:

| Arm | MTP | Wall | Pass | Review | Fail | Error |
|---|---|---:|---:|---:|---:|---:|
| A1 | off | 3401.8 s (56.7 min) | 50 | 239 | 55 | 23 |
| A2 | off | 2968.5 s (49.5 min) | 52 | 244 | 59 | 12 |
| Median A | off | 3185.2 s | | | | |
| B1 | k=1 | 3315.6 s (55.3 min) | 53 | 229 | 55 | 30 |

B1 vs median A: **+4.1% slower** (gate needed >= 5% faster). B1 vs A1: -2.5%. B1 vs A2: +11.7%. A1/A2 already differ by 433 s (13.6%). B1 sits inside that AA spread, on the slow side.

vLLM counter deltas (`prompt_tokens_total` / `generation_tokens_total`):

| Arm | Prompt tokens | Gen tokens | Implied gen tok/s (gen / wall) |
|---|---:|---:|---:|
| A1 | 27,244,444 | 299,157 | 87.9 |
| A2 | 22,752,488 | 254,137 | 85.6 |
| B1 | 18,561,154 | 220,331 | 66.4 |

MTP counters on B1 only (post minus pre):

| | Count |
|---|---:|
| Draft tokens | 114,198 |
| Accepted tokens | 105,350 |
| Acceptance | 92.3% (gate >= 70%: pass) |

Smoke: P4185R0 parsed (`status=ok`, verdict=review). P4182R0 failed IdealVerification `string_too_long` (same class as Arm A, not empty content). Smoke acceptance 2871/2936 = 97.8%. No #34650 empty `content` / `reasoning_content` on the successful paper.

## Output quality check

Non-error verdict flips (sidecar `suggested_verdict`):

| Pair | Both-ok | Real flips | Rate |
|---|---:|---:|---:|
| A1 vs A2 (noise floor) | 348 | 53 | 15.2% |
| A1 vs B1 | 331 | 49 | 14.8% |
| A2 vs B1 | 341 | 50 | 14.7% |
| B1 vs stable AA pair | 277 | 22 | 7.9% |

MTP did not add verdict noise above AA. Quality-stability is acceptable. That is not enough to keep MTP without a wall win.

JSON / error rate (CLI footer): A1 23/367 (93.7% ok), A2 12/367 (96.7% ok), B1 30/367 (91.8% ok). Gate: JSON >= baseline A: fail.

B1 sidecar error classes (37 error sidecars; CLI footer counted 30 paper errors): metadata/outline 15, StepError 12, timeout 5, IdealVerification / quote length 3, MalformedModelOutput 2. These are the same families as Arm A, not a new MTP empty-output class.

## Why k=1 can look worse (and why fewer tokens are not a win)

MTP drafted well. The promise is fewer sequential decode steps. That only pays when outputs are long enough to amortize draft+verify, and when the batch is not already full.

This fleet is the other regime: short judge JSON, long prompts, S=16 packed. k=1 saves at most one extra token per step. Every step still pays the MTP head. On a full batch that extra compute competes with useful sequences. Acceptance can be green and throughput still falls.

The smaller B1 token totals are not a speedup:

- A1 vs A2 (both MTP off) already swings 27.2M vs 22.8M prompt and 299k vs 254k gen. Token volume is not a stable work meter on a shared pod.
- B1 generated 220k tokens in 3316 s. That is worse gen tok/s (66.4 vs ~86), not "MTP used tokens more efficiently."
- B1 had more errors (30 vs 23/12). Failed papers emit less JSON and still occupy wall.
- After the restart the prefix cache was cold (B1 hit rate 18.1% vs ~93% on the long-lived A pod). That handicaps B1 wall. A deltas may also include foreign load. Even with that caveat, we do not have a measured win.

Fair metric: same 367 papers, wall and gen tok/s. Both say no.

## k=2 / k=4: do not run

V4-Pro ships one MTP head (`num_nextn_predict_layers: 1`). k=2 reuses that layer. We already have 92.3% accept at k=1 and no wall win. Deeper draft throws away more rejected tokens.

Public record in this regime (web sweep, same model family / same packed-batch shape):

- GB300 blog: ISL=2k / OSL=64, MTP cannot amortize
- vLLM PR #12755: ~1.63x at QPS=1, ~1.0x at QPS=8
- InferenceX H200 V4-Pro: about -3.4% tok/s at high throughput; wins only at low/mid concurrency
- canada-quant: 91-93% accept on V4-Pro; Flash k=2 about -86% tok/s at bs=8
- vLLM #47277 / #41603: high accept, flat or negative throughput
- NVIDIA 8x H200 V4-Pro recipe ships MTP off
- Unsloth 1.5-1.9x figures are DSpark, not MTP. Different module, different checkpoint.

Same shape as the 9B llama.cpp row already on this issue: n-max=2 helped that local decode-heavy bench; n-max=4 fell below baseline on prose. Our pod workload is the JSON / packed-batch side. Raising k will not flip the sign.

## Decision

- Alliance-pod DeepSeek / vLLM MTP k=1: **no-go. Revert.**
- k=2 / k=4 on this pod: **do not productize, do not A/B.**
- Qwen3.8-27B Q4 on the 3080: still **no-go** (does not fit). Unchanged.
- 9B llama.cpp proxy on this issue: still a local method check only.

Revert for Sam: remove the two appended flags and restart.

```
--speculative-config '{"method":"mtp","num_speculative_tokens":1}' --compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'
```

Writeup in-repo: `packages/whisker/research/mtp-ab-experiment/RESULTS.md`. Gate: ADR-014.
