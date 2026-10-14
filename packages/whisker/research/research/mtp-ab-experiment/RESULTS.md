# MTP k=1 A/B on alliance-pod

Date: 2026-08-25 (Arm A) / 2026-08-26 (Arm B)
Pod: vLLM 0.24.0, DeepSeek-V4-Pro, 8x H200, `--max-num-seqs 16`
Client: `whisker-tapetum-llm --review-all --force --concurrency 32 --trace`
N (num_speculative_tokens): 0 on A, 1 on B. Not 2.

## Verdict

Revert. MTP k=1 works (acceptance 92.3%) and does not raise verdict-flip noise above the AA floor, but wall time did not improve and JSON/error rate got slightly worse. ADR-014 requires a material wall win. Keep MTP off.

## Methodology

Load-matched A/B on the shared alliance-pod.

- Arm A1, A2: MTP off (no `spec_decode_*` counters). Same 367 `--review-all` PIDs, back to back.
- Sam applied `--speculative-config '{"method":"mtp","num_speculative_tokens":1}'` plus `--compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'` and restarted.
- Smoke: P4182R0 + P4185R0. P4185R0 parsed (`status=ok`, verdict=review). P4182R0 failed IdealVerification `string_too_long` (same class as Arm A, not empty content). Acceptance during smoke: 2871/2936 = 97.8%.
- Arm B1: identical client command, MTP k=1.

Sidecar snapshots: `snapshots/llm-a1/`, `llm-a2/`, `llm-b1/`.
Metrics scrapes: `metrics/`.

## Fleet counts (CLI footer)

| Arm | Wall (s) | Pass | Review | Fail | Error | Model retries |
|-----|----------:|-----:|-------:|-----:|------:|--------------:|
| A1 (MTP off) | 3401.8 | 50 | 239 | 55 | 23 | 24 |
| A2 (MTP off) | 2968.5 | 52 | 244 | 59 | 12 | 14 |
| B1 (MTP k=1) | 3315.6 | 53 | 229 | 55 | 30 | 15 |

Median(A1, A2) = 3185.2 s.

## ADR-014 gate

| Metric | Source | Gate | Result | Pass? |
|---|---|---|---|---|
| MTP acceptance | B1 delta `accepted / draft` | >= 70% | 105350 / 114198 = 92.3% | yes |
| Wall | B1 vs median(A1, A2) | material better, target >= 5% | 3315.6 vs 3185.2 = +4.1% slower | no |
| Verdict flips | sidecar `suggested_verdict` | flip_AB <= flip_AA + margin | AA 15.2%; A1-B1 14.8%; A2-B1 14.7% | yes |
| JSON validity | CLI error count | >= baseline A | B1 30 errors (91.8%) vs A1 23 (93.7%) / A2 12 (96.7%) | no |
| Prefix cache | hit rate B vs A | no significant drop | B1 18.1% vs A ~93% | confound (see below) |

Decision: fail. Revert MTP and CUDA-graph flags.

## Wall detail

- B1 vs A1: -2.5% (slightly faster than the slower baseline)
- B1 vs A2: +11.7% (slower than the faster baseline)
- B1 vs median: +4.1%

A1/A2 already differ by 433 s (13.6%). B1 sits inside that AA wall spread, on the slow side of the median. No material win.

Caveat: Arm A ran on a long-lived pod with ~93% prefix-cache hits. Arm B ran after Sam's restart, so the prefix cache was cold (18.1% hits on the B1 delta). That handicaps B1 wall and is not an MTP defect. Even with that handicap removed in a later warm-cache rerun, we do not have a measured win today, so the gate stays fail.

## Flip detail (non-error papers only)

| Pair | Both-ok | Real flips | Rate |
|---|---:|---:|---:|
| A1 vs A2 (noise floor) | 348 | 53 | 15.2% |
| A1 vs B1 | 331 | 49 | 14.8% |
| A2 vs B1 | 341 | 50 | 14.7% |
| B1 vs stable AA pair | 277 | 22 | 7.9% |

MTP did not add verdict noise beyond run-to-run AA. Quality-stability is acceptable. That is not enough to keep it without a wall win.

## Smoke

- `/version` 0.24.0, model id `deepseek-v4-pro` unchanged.
- `spec_decode_*` counters present after restart.
- Pre-smoke already showed 2030/2090 = 97.1% (foreign/warmup traffic).
- No empty `content` / `reasoning_content` trap (#34650) on the successful paper.

## Foreign load

- Pre-A1: 0 running, 0 waiting
- Pre-A2: 1 running, 0 waiting
- Pre-B1: 0 running, 0 waiting
- Post-B1: 0 running, 0 waiting

No obvious foreign-load contamination of B1.

## Revert for Sam

Remove the two appended flags and restart:

```
--speculative-config '{"method":"mtp","num_speculative_tokens":1}' --compilation-config '{"mode": 3, "cudagraph_mode": "FULL_DECODE_ONLY"}'
```
