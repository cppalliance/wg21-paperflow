# CARD: 05v — `VLLM_BATCH_INVARIANT` throughput cost

## Bottom line
`VLLM_BATCH_INVARIANT=1` is a determinism switch that intentionally slows inference. Official docs and PR #30018 say ~50% throughput cut; MTP field repro ~3× decode slowdown. Reject for the cold-run ≤10 min speed path. Leave off unless a separate bit-exact campaign accepts a large wall regression.

## Numbers
- PR #30018: ~**50%** throughput reduction with BI on.
- Issue #42518 (MTP): ~**75→23 tok/s** with BI (~**3×** slowdown).
- Default: off (`getenv` default `"0"`); feature still **beta**.
- Arithmetic: ~2× `L_eff` doubles wall at fixed N and S=16 (e.g. ~1400 s → ~2800 s), moves away from 600 s.
- DeepSeek-V4-Pro not on documented tested-model list for BI.

## Architecture implication
Speed path and bit-exact CI are separate knobs. Fleet quality-stability remains “same findings,” not bit-exact (`MODELS.md`). Do not bundle BI with MTP/CUDA/DeepEP speed flags.

## Reject-or-A-B
- **REJECT for speed path** — never enable `VLLM_BATCH_INVARIANT` for throughput or cold wall.
- **Not an A/B for ≤600 s.** Separate campaign only if goal flips to bit-exact identity.
- Reopen only if upstream ships ≤5% tax on H200 TP8 V4-Pro continuous batching, measured on alliance-pod.

## Links
- Source: `05v-web-batch-invariant.md`
- Related: `103-vllm-mtp-determinism.md`, `MODELS.md`, `00-baseline.md`
- https://docs.vllm.ai/en/stable/features/batch_invariance/
- https://github.com/vllm-project/vllm/pull/30018
- https://github.com/vllm-project/vllm/issues/42518
