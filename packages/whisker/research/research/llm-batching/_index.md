# _index - llm-batching

Self-target research (no external clone). Keyed on the analyzed state, not a git SHA.

- slug: llm-batching
- target: packages/whisker tapetum_llm batch path + read-only pipeline call path
- analyzed: 2026-07-07
- corpus state: 200-paper run @ c=3, 2159.8 s, vLLM 0.24.0, post base64-filter
- artifacts: 00-baseline.md, 05a-05e web cards, 11-19 personas, SYNTHESIS.md
- re-run trigger: cli.py/adjudicate.py concurrency changes land, pod flags
  change (max-num-seqs, prefix caching), or twin pod comes online
