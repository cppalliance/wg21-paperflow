# Arm A Results (Baseline, MTP OFF)

## Wall Times
- A1: 3401.8s (56.7 min), 367 evaluated, 50 pass / 239 review / 55 fail / 23 error
- A2: 2968.5s (49.5 min), 367 evaluated, 52 pass / 244 review / 59 fail / 12 error
- **Median wall: 3185.2s (53.1 min)**

## AA Verdict Flip Rate (run-to-run noise floor)
- Common PIDs: 383
- Both non-error: 348
- Real verdict flips: **53 / 348 = 15.2%**
- Transition breakdown:
  - fail -> review: 21
  - review -> fail: 20
  - review -> pass: 8
  - pass -> review: 3
  - pass -> fail: 1
- A1 errors: 30, A2 errors: 19

## Metrics Delta (A1 run)
- Prompt tokens: 4.1278e9 - 4.1005e9 = 27.24M tokens processed
- Generation tokens: 14.04M - 13.74M = 299K tokens generated
- Prefix cache: hit rate ~93% during run

## Foreign Load
- Pre-A1: 0 running, 0 waiting
- Pre-A2: 1 running, 0 waiting (minimal foreign load)
- Post-A2: 0 running, 0 waiting
