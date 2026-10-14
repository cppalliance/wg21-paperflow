# 01 - olmocr-llm-judge

**Verdict:** usable-with-conditions — olmOCR-bench is a strong deterministic multi-stratum fusion and reporting reference, but it has no runtime LLM-as-judge scoring lane to copy for tapetum.
**Confidence:** high

## Findings

- [CRITICAL] olmOCR-bench does **not** use an LLM-as-judge at evaluation time; every scored unit is a deterministic binary fact check via `test.run(md_content)` returning `(passed, explanation)`. Evidence: `benchmark.py:116-127`, `tests.py:114-125`, `olmocr/bench/README.md:250-251` ("All facts checked about documents are either pass/fail"). GPT-4o, Gemini-Flash-2.0, and Claude-Sonnet-3.7 appear only in **offline test curation** when building JSONL facts, not when scoring candidate output (`olmocr/bench/README.md:218-234`). Impact: goal 1 (keep LLM scoring) must stay on tapetum; olmOCR cannot supply judge prompts, rubrics, or model-based verdict fusion.

- [HIGH] Leaderboard "Overall" is a **macro-average of per-JSONL stratum pass rates**, not a micro-average over all tests and not a det+LLM merge. Evidence: `benchmark.py:343-350` computes per-category pass rates; `benchmark.py:387-388` sets `new_overall_score = sum(jsonl_pass_rates) / len(jsonl_pass_rates)`; README leaderboard columns show each stratum separately plus Overall (`olmocr/bench/README.md:23-36`). Impact: goal 3 — adopt the same anti-collapse rollup for a merged report (e.g., macro-average of `{det_pass, llm_pass}` bits per axis/stratum) while keeping both lane columns visible like the README table.

- [HIGH] Benchmark run does **not** persist per-document numeric score sidecars; scores are in-memory structures plus optional aggregate artifacts. Evidence: `test_results` nested dict `candidate → pdf → page → [(test, passed, explanation)]` built during run (`benchmark.py:57-130`); terminal summary only (`benchmark.py:352-414`); optional `--test_report` HTML (`benchmark.py:417-418`) and `--output_failed` JSONL of failing **test definitions** (`benchmark.py:421-455`), not per-PDF scores. Committed facts live in JSONL (`tests.py:870-880`); candidate OCR output is page-level MD files `{base}_pg{N}_repeat{R}.md` (`benchmark.py:66-67`). Impact: goal 2 — whisker's `<pid>.whisker.json` sidecar is already ahead; borrow olmOCR's nested `test_results` shape for drill-down fields inside a unified sidecar, not their lack of per-doc persistence.

- [MED] "Confidence" in olmOCR means **bootstrap CI on pass rates**, not model self-reported confidence. Evidence: `calculate_bootstrap_ci` resamples within JSONL strata then averages category means (`utils.py:47-60`); invoked with `splits=jsonl_file_sizes` (`benchmark.py:328-330`); CLI `--confidence_level` default 0.95 (`benchmark.py:183-186`). No field analogous to tapetum `confidence [0..1]` (00-baseline:29). Impact: merged reporting can pair tapetum model confidence with deterministic bootstrap CI as two different "confidence" lanes rather than conflating them.

- [MED] Invalid, missing, or errored eval inputs fail hard or return **None**, never a partial score mistaken for complete. Evidence: missing MD repeats → `candidate_errors`, overall 0.0 (`benchmark.py:69-77`); `test.run` exceptions logged and counted as failure (`benchmark.py:121-123`); GRPO `evaluate_single_completion` returns `(i, None, None)` for invalid completion type, missing metadata, or load errors (`grpo_train.py:604-611`, `677-679`). Impact: goal 3 must treat absent/errored tapetum sidecars like olmOCR treats missing candidates — explicit absent lane, not imputed pass (cf. 00-baseline:51, six tapetum JSON errors).

- [MED] Stochastic OCR outputs use **majority voting across repeats** before a fact is pass/fail. Evidence: `test_avg = repeat_passes / num_repeats`; `final_passed = test_avg > 0.5` (`benchmark.py:125-126`); `--repeats` supported in `run_benchmark.sh` (cited in redteam §1.9). Impact: if tapetum ever multi-samples, same >0.5 rule is portable; current whisker serial adjudication does not need it yet (00-baseline: C3).

- [LOW] Training stack uses Claude-derived **reference rewards**, not benchmark-time judging. Evidence: `reward_front_matter` scores parse success plus field match vs `claude_original` (`grpo_train.py:801-809`); `bench_edit_distance_reward` compares completions to Claude reference text (`grpo_train.py:682-697`); primary RL reward is still deterministic `olmocr_bench_reward` = test pass proportion (`grpo_train.py:1093-1166`). Impact: do not port these into tapetum adjudication; they optimize the OCR model, not QA reporting.

- [LOW] Human curation metadata on facts uses `checked: verified|rejected` with atomic JSONL rewrite via review app (`tests.py:36-38`, `101`; `review_app.py:66-81`, `127-147`). Impact: goal 2 — optional `"llm_reviewed": true` or axis-level `checked` on tapetum findings mirrors olmOCR's governance without merging lanes into one verdict (C1).

## False-pass hypothesis

A merged det+LLM score computed as macro-average pass-bits across strata (olmOCR-style `benchmark.py:387-388`) could **pass** a paper whose deterministic lane fails localized table facts while tapetum pass-bit is 1 on prose-heavy axes — the same anti-collapse failure mode olmOCR guards against for NID-like strata hiding table regressions (redteam §1.4), now with an LLM lane that disagrees with whisker on 123/194 papers (00-baseline:49).

## False-fail hypothesis

If merge requires **both** lanes to pass (AND), a paper where olmOCR-style majority-repeat would pass (`test_avg > 0.5` at `benchmark.py:126`) but one tapetum axis fails with `confidence: 0.95` would be **false-failed** — analogous to olmOCR counting a fact failed when only minority repeats fail, while whisker deterministic lane might still be `review`.

## What would change my mind

Discovery of any olmocr module that calls an external LLM API at benchmark time with a rubric/judge prompt to score conversion output (structured or free-text) and folds that score into the leaderboard alongside deterministic facts — none found under `olmocr/bench/` or `olmocr/train/grpo_train.py` eval paths in this read.
