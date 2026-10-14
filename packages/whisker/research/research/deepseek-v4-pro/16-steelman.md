# 16 - Steelman

**Verdict:** usable — DeepSeek-V4-Pro is a strong fit for tapetum_llm because the lane is advisory-only with layered deterministic guardrails that convert model weaknesses into harmless "review" signals, while V4-Pro's open-weight sovereignty, coding/long-document strengths, and proven sighting-run yield match the lane's actual job.
**Confidence:** high

## Findings

- [HIGH] **The lane never gates; model errors cannot ship broken papers.** Evidence: `packages/whisker/src/whisker/CLAUDE.md:361-371` — tapetum_llm is opt-in, never in the `whisker --gate` CI contract, never overwrites the whisker verdict on record. Impact: the worst-case outcome of a wrong advisory call is a human looks at a paper that did not need it, or misses a hint they would have gotten anyway. This is the architectural precondition that makes a 94% abstention-failure rate survivable.

- [HIGH] **Four deterministic safety nets absorb the known failure modes before any human trusts the output.** Evidence: `grounding.py:24-56` (verbatim + fuzzy substring match, ungrounded quotes dropped); `adjudicate.py:234-246` (sub-floor confidence -> forced `review`; ungrounded non-pass -> `review`; partial read -> never clean `pass`); `constants.py:28,35` (`CONFIDENCE_DECISION_FLOOR = 0.50`, `SEVERITY_MAJOR` fold); `chunking.py:38-46` (severity-aware worst-axis re-derived in Python, overriding model overall verdict). Impact: hallucinated evidence, miscalibrated confidence, and cosmetic structural noise are structurally demoted. The lane is engineered for exactly the failure profile V4-Pro exhibits.

- [HIGH] **Empirical sighting run on alliance-pod validates the design with real WG21 corpus data.** Evidence: `packages/whisker/research/tapetum-sighting-run-2026-07-01.md` — 196/201 papers adjudicated; **72 `review -> pass`** (advisory clears false alarms); **6 `fail -> review`** rescues (false-fail population); P3941R4 heading-monotone rescue at confidence 0.95 with `structure`/`minor`/`review` exactly as rubric specifies; 7-chunk P2728R12 with zero 413s. Impact: V4-Pro already delivers the two populations the lane exists for. JSON parse failures (5 papers) demote to pipeline fallback `review` at confidence 0.0, not silent pass.

- [HIGH] **Model sovereignty, MIT license, and per-hour pod billing align with project invariants and remove operational friction.** Evidence: `00-baseline.md:14-15,73-80`; root `CLAUDE.md` model-sovereignty section; whisker CLAUDE.md:401-406. Impact: no cloud API deprioritization, no content filtering, no per-token rationing. Run the full 201-candidate set anytime.

- [MED] **V4-Pro is the strongest open-weight model available and near-parity with Opus 4.6 on the axes tapetum cares about most.** Evidence: `00-baseline.md:32-45` — SWE-bench Verified 80.6% vs Opus 80.8%; LiveCodeBench 93.5% vs 88.8%; Terminal-Bench 67.9% vs 65.4%; MMLU-Pro 87.5%; LongBench-V2 51.5 (leads open models). NIST CAISI (~8-month lag vs US frontier) measures general agentic reasoning, not "read markdown and cite a substring."

- [MED] **H2-chunking and 393K configured window keep individual calls below the long-context degradation cliff.** Evidence: `constants.py:44` (`MAX_PAPER_MD_CHARS = 500_000`); `00-baseline.md:192-195` (MRCR 8-needle ~0.82 at 256K, ~0.59 at 1M); sighting run P2728R12 7-chunk success.

- [MED] **The task shape favors V4-Pro: structured JSON adjudication over English markdown, not open-ended generation.** Evidence: `Adjudication` schema 7 fields; `reasoning` field first (deliberate-before-commit); thinking block stripped before JSON extraction; English thinking default. Impact: the 94% AA-Omniscience hallucination rate measures "answer anyway on trivia," not "quote a substring from a document you were just shown." Grounding converts invention attempts into dropped spans.

- [LOW] **Self-hosted serving gives full control over the parameters that matter for determinism.** Evidence: `temperature=0.0`, `seed=0`, `parallel_tool_calls=False`, serial semaphore (D11). MoE routing variance under shared load is the remaining risk; alliance-pod dedicated uptime mitigates batch-composition effects.

## False-pass hypothesis

A token-preserving table cell swap in a pass-tier paper with lossy-table risk signal: V4-Pro triages `pass` at confidence 0.88 with one grounded but irrelevant quote from the same table. Decide does not demote (confidence above floor, evidence grounded). **Mitigation already in place:** the paper was selected precisely because whisker flagged `lossy_table_count > 0`; the advisory `pass` does not change whisker's pass verdict; a human reviewing `--inspect` side-by-side still sees whisker risk signals.

## False-fail hypothesis

tomd-normalized template spacing (`template <typename T >`) flagged as code-axis `fail`/`major`, demoted to `review` only if severity is mislabeled `major`. **Mitigation:** severity-aware decide folds non-major fails to `review`; even a false `review` on a whisker-pass paper costs one human glance, not a CI block.

## What would change my mind

If a labeled holdout of >=50 tapetum candidates showed V4-Pro advisory **fail** suggestions (post-decide) on clean conversions at >15% rate **and** human annotators agreed those fails were wrong **and** the failures were not demotable to `review` by existing guardrails — proving the safety nets are insufficient for this model specifically.
