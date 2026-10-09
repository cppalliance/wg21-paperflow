# Research index - tapetum-llm-speedup

- Target: whisker-tapetum-llm fleet throughput (in-workspace) vs docling,
  langextract, marker, olmocr, MinerU, unstructured, vllm, sglang, nougat,
  surya, deepeval, promptfoo, ragas, litellm (cloned to _scratch).
- Workspace HEAD at research time: 51cb704
- Date: 2026-07-23
- Swarm: 150 Composer 2.5 subagents (1 cloner, 5 web foragers, 138 personas,
  6 verifiers), Fable 5 orchestration, Opus-tier meta-review.
- Deliverable: SYNTHESIS.md (packages CONSERVATIVE ~11-14 min, MODERATE
  ~9-11 min, AGGRESSIVE not reliably <=5 min; warm 65 s -> ~10-15 s).
