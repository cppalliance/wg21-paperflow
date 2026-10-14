# 17 - Steelman

**Verdict:** usable-with-conditions — The stack implements the only externally validated comprehension-gating pattern (olmOCR-style deterministic fact assertions + one-time LLM read-back anchor), converges with 2026 field direction (ParseBench/RealDocBench), and respects every root invariant; it is positioned correctly but not yet proven at corpus scale.
**Confidence:** high

## Findings

- [HIGH] Lane 3 is architecturally aligned with olmOCR-Bench, the sole comprehension-gating benchmark among 28 surveyed converters, not an ad-hoc invention. Evidence: olmOCR uses 6 assertion classes (presence, absence, reading order, table neighbors, math, baseline) with strictly deterministic pass/fail and explicit rejection of LLM-as-judge (`05-web.md` Q1: https://github.com/allenai/olmocr/tree/main/olmocr/bench, https://olmocr.allenai.org/papers/olmocr.pdf); whisker implements the same five substantive types at `facts.py:59-64` and documents the olmOCR adoption in `packages/whisker/research/comprehension-poc-report.md:28-32`. Impact: the design is not a local quirk; it tracks the only published converter QA that tests fact recovery rather than edit distance.

- [HIGH] The 2026 benchmark literature independently converges on deterministic assertion gating over LLM judges and structural fidelity alone, validating whisker's core bet. Evidence: ParseBench (169K deterministic rules, explicitly rejects LLM-as-judge and TEDS gating) and RealDocBench (field-level typed gold, decoupled from formatting) both arrived at comprehension-style QA without LLM judges (`05-web.md` Q3: https://arxiv.org/abs/2604.08538, https://arxiv.org/html/2606.07401); OmniDocBench and opendataloader-bench remain structural-only (`05-web.md` Q3). Impact: whisker is ahead of TEDS/edit-distance gating and aligned with where the field is moving, not behind it.

- [HIGH] The three-layer split (deterministic CI gate + one-time empirical anchor + opt-in advisory LLM lane) is the correct architecture for root CLAUDE.md invariants, not a compromise. Evidence: Lane 3 runs with no LLM in the scoring loop (`facts.py:372-388`, `00-baseline.md:32-34`); read-back is explicitly out-of-band for determinism, cost, and model-sovereignty (`packages/whisker/src/whisker/CLAUDE.md:341-349`); tapetum_llm "NEVER hard-fails, is never in the `whisker --gate` CI contract" (`CLAUDE.md:361-371`) with one-way import isolation (`CLAUDE.md:408-409`). Impact: the stack cannot silently trade reproducibility for convenience; each layer has a documented authority boundary.

- [HIGH] The comprehension gate has teeth, not vacuous green. Evidence: CI asserts at least one verified fact per corpus member (`test_comprehension_corpus.py:67-70`); scrambled-table canary flips `tableA-gpu-coro-no` (`test_comprehension_corpus.py:77-95`); scrambled-formula canary flips `math-even-power-nonneg` (`test_comprehension_corpus.py:98-116`); anti-vacuous suite guard (`test_comprehension_corpus.py:52-57`). Impact: Lane 3 would catch the table-cell and formula corruptions that Lane 2 fidelity metrics are documented to wave through (`CLAUDE.md:38-41`).

- [MED] Provenance discipline on facts is genuinely rigorous and prevents "authoritative" tests from unreviewed drafts. Evidence: only `checked == "verified"` promotes to enforced (`facts.py:66-68`, `facts.py:124-130`); drafts are evaluated but explicitly tagged "(unverified, not gated)" (`facts.py:383-387`); authoring workflow requires human verification against source before flip (`CLAUDE.md:351-353`, `comprehension-poc-report.md:47-49`). Impact: the comprehension corpus is epistemically honest; a fact cannot accidentally become a CI gate without a deliberate blessing step matching olmOCR's `checked: VERIFIED | REJECTED` pattern (`05-web.md` Q1 DeepWiki card).

- [MED] The one-time LLM read-back anchor closes the proxy loop with documented evidence, not hand-waving. Evidence: P4182R0 passed 3x 8/8 including both table cells on byte-exact run 3 (`corpus/P4182R0.validation.md:43-52`, `00-baseline.md:61-64`); P4185R0 passed 9/9 with all four math formulas verbatim (`corpus/P4185R0.validation.md:53-58`, `00-baseline.md:62-63`); methodology rejects resemblance round-trips in favor of question answering (`P4182R0.validation.md:18-21`). Impact: the deterministic facts are empirically anchored as a faithful proxy for what downstream LLMs recover, justifying CI substitution without putting an LLM in the gate.

- [MED] Known limitations are documented honestly rather than buried, which is itself a strength for adoptability. Evidence: calibration edges "provisional, not yet fitted on our own labeled corpus" (`CLAUDE.md:316-321`, `00-baseline.md:86-88`); corpus size "2 members" against ~200 converted papers (`00-baseline.md:53-57`, `00-baseline.md:77-79`); `ovr` explicitly "only a display composite" and misleading vs `uni`/`qa` (`CLAUDE.md:356-359`); tapetum #277 blocking conditions listed with file:line status (`00-baseline.md:71-76`, `00-baseline.md:84-85`). Impact: a reviewer can trust the team's self-assessment; the gap between design intent and current proof is transparent, not hidden.

- [LOW] The research trail under `packages/whisker/research/` is unusually deep for a QA subsystem and supports informed iteration, not blind expansion. Evidence: 28 per-converter red-team reports including olmOCR gap analysis (`redteam/olmocr.md:1-7`); comprehension POC with full command log (`comprehension-poc-report.md`); tapetum sighting run on 196/201 papers (`00-baseline.md:65-67`); 31 cloned benchmark repos (`00-baseline.md:109-116`). Impact: future corpus growth and threshold calibration have a mapped prior-art landscape rather than starting from zero.

## False-pass hypothesis

A converted paper with **zero** `checked: verified` facts in its `.facts.jsonl` passes Lane 3 vacuously (`facts.py:128-130`: "a paper with no verified facts passes"), so the comprehension gate proves nothing for the ~198 papers not yet in the corpus. The CI suite guards against an empty corpus (`test_comprehension_corpus.py:52-57`) but cannot guard per-paper vacuity outside the two committed members.

## False-fail hypothesis

A `present` fact with tight `max_diffs` could fail on benign Unicode or whitespace normalization that still leaves the markdown fully LLM-readable (rapidfuzz window + exact DP at `facts.py:214-236`), rejecting a shippable conversion on a formatting delta rather than a comprehension loss.

## What would change my mind

A labeled corpus of 30+ papers spanning adversarial tables, display math, code-heavy, and multi-column layouts, each with source-verified facts and a fresh blind read-back anchor matching the deterministic gate at >=95% fact recovery, would flip the verdict from usable-with-conditions to usable as a general #254 proof.

## Where the steelman ends (criticisms that cannot be argued away)

These remain fair hits even on the strongest reading:

1. **Corpus coverage is 2 papers vs ~200 converted** (`00-baseline.md:77-79`). No adversarial multi-column/merged-cell table paper, no code-heavy paper, no image-ref fact type. Selection bias is real until breadth grows.

2. **#277 blocking condition 1 is still open.** `adjudicate.py:237` demotes ungrounded non-pass verdicts to review but does not demote a confident `pass` whose evidence spans were all dropped by grounding (`00-baseline.md:71-76`). The advisory lane can still emit a misleading clear signal.

3. **Fact schema gap vs tapetum axes.** Five fact types vs seven tapetum axes; no `code`, `xref`, or `image-ref` type (`00-baseline.md:80-83`). Lane 3 cannot express several risk classes the advisory lane was built to hunt.

4. **72 review->pass tapetum clears remain unaudited** (`00-baseline.md:84-85`, blocking condition 2). The sighting run is exploratory, not ground-truthed.

5. **Thresholds are adopted constants, not fitted operating points** (`CLAUDE.md:316-321`). Review-biased until calibration runs on a labeled set.

6. **olmOCR operates at 7,010 tests across 1,403 PDFs** (`05-web.md` Q1); whisker's two-paper micro-corpus is the right pattern at the wrong scale for claiming field-parity coverage today.
