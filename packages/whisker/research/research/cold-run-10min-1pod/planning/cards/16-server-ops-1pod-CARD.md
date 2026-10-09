# CARD: Server ops checklist — alliance-pod only (no seq raise)

## Bottom line (3 sentences max)
Server-only ops on `alliance-pod` save **~5–9 min** on the 3003 s baseline and **~3–7 min** post-short-circuit; they do **not** reach ≤10 min alone. Keep `--max-num-seqs 16` (16→32 was +57% wall). Client v11 call cuts and other levers remain mandatory.

## Numbers that matter
- Raw baseline **3003 s** / post-SC ~**1921 s** (N=1419); scale savings × **0.621** after short-circuit
- Recipe bundle (Tier 1): **300–550 s** on 3003; max optimistic (recipe+DeepEP/DBO+EPLB) ~**680 s**
- Post-SC max optimistic ~**422 s** → still ~**25 min** wall, not 10
- Compute term alone on 1419 @ S=16: **1774 s** before L cuts
- MTP gate: `spec_decode_draft_acceptance_rate` ≥**70%**; k=**1** only

## Architecture implication
Ops-only (pod restart / image bump): MBT 16384, APC + retention (#43447), MTP k=1, CUDA graphs FULL_DECODE_ONLY, long-prefill 8192; then A/B DeepEP low-latency + DBO + async EPLB. Confirm build ≥ PR #43447 before APC. Anti-knobs: seqs>16, c>32, deepep_high_throughput, MTP k≥2, FlashInfer MoE without A/B. Rollout: Tier1 smoke → cold fleet → Tier2; revert MTP first on regression.

## Cite / do not re-open
- Raising `--max-num-seqs` to “speed up”
- Claiming server flags close the ~800–900 s MODERATE gap
- APC done on pre-#43447 (0% hits false-pass)
- Mixing raw-3003 and post-SC savings without rescaling

## Links to related reports
- `research/cold-run-10min-1pod/16-server-ops-1pod.md` (this source)
- `00-baseline.md`, `11-wall-arithmetic-1pod.md`
- Prior: `cold-run-10min/{26-server-ops-checklist,64-flashinfer-moe-kernels,05c-web-moe-batching,05d-web-mtp-specdecode}.md`
