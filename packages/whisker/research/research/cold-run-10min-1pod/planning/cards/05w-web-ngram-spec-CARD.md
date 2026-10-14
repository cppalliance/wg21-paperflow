# CARD: 05w — N-gram / prompt-lookup speculative decoding vs MTP

## Bottom line
Ngram/PLD is a real zero-draft-weight speculative path for templated JSON keys/punctuation, but a weak substitute for native MTP on DeepSeek-V4-Pro and only a marginal UnitCheck L lever at short OSL (~20–77 tok). Prefer MTP k=1 on alliance-pod; keep ngram as fallback for dense endpoints without MTP.

## Numbers
- Acceptance: ngram **~10–90%+** (bimodal) vs MTP **~50–70%** more stable (survey); V4 MTP healthy often **~80–90%**.
- UnitCheck P50 pass ~**77 tok** (~**55** in `reasoning`); `UnitCheckClear` ~**20 tok**.
- Optimistic wall_save at 15% decode cut on 663 survivors: **~(663×0.9)/16 ≈ 37 s**; 30% → ~**75 s** (vs ~800–900 s gap).
- Structured risk: `prompt_lookup_min=2` corrupted tool/JSON (~50%→**100%** clean at min=**8**, #40875).
- Config class: pod-restart `method: "ngram"`; no draft weights.

## Architecture implication
One speculative `method` — ngram instead of MTP is a downgrade on V4-Pro. If tried on schema-heavy prompts: `prompt_lookup_min≥8`, small k (2–3), measure acceptance + JSON validity + verdict flip. Best use: dense offload models without MTP, or MTP acceptance collapsed.

## Reject-or-A-B
- **Prefer MTP k=1** on alliance-pod (do not replace without A/B proof MTP is broken).
- **A/B optional:** ngram (min=8, k=3) vs MTP k=1 vs neither on real unit traffic.
- **Reject as ≤600 s primary lever:** ngram alone (tens of seconds, not minutes).
- **Garbage flip:** acceptance stays <~30% on pass-path or structured corruption at min=8.

## Links
- Source: `05w-web-ngram-spec.md`
- Related: `05d-web-mtp-specdecode.md`, `15-verdict-first-design.md`, `16-server-ops-1pod.md`
- https://docs.vllm.ai/en/stable/features/speculative_decoding/n_gram/
- https://github.com/vllm-project/vllm/issues/40875
- https://friendli.ai/blog/n-gram-speculative-decoding
