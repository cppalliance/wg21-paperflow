# 17 - Steelman

**Verdict:** usable-with-conditions — LangExtract is not a wholesale replacement for tapetum_llm, but its post-LLM grounding stack and index-ordered batching patterns are battle-tested mechanisms we should selectively port, not dismiss because the library is cloud-first.
**Confidence:** high

## Findings
- [CRITICAL] The monotonic exact-occurrence DP (`_select_monotonic_matches` / `_apply_monotonic_exact_matches`, `resolver.py:1113-1243`) solves repeated-mention alignment: when the same entity or quote appears multiple times in source text, extractions in model output order map to successive, non-overlapping token positions via a weighted frontier DP, not the first substring hit. Evidence: baseline DQ3 (`00-baseline.md:63`) contrasts this with our document-level `norm_quote in norm_md` (`whisker/tapetum_llm/grounding.py:49-50`), which has no occurrence ordering and returns no spans.
  Impact: For tapetum evidence quotes on papers that repeat section titles, normative wording, or table headers, this is the single highest-value mechanism LangExtract offers that our 56-line `ground_spans` cannot approximate.

- [HIGH] Every grounded extraction carries a graded `AlignmentStatus` (`MATCH_EXACT | MATCH_LESSER | MATCH_FUZZY`, `core/data.py:43-47`) plus `char_interval` and `token_interval` (`resolver.py:1231-1241`, `resolver.py:327-398`). Evidence: maintainer Issue #259 (https://github.com/google/langextract/issues/259) confirms offsets are computed by post-LLM alignment, not model-emitted; baseline DQ3 (`00-baseline.md:63`).
  Impact: Our lane drops ungrounded quotes silently (`grounding.py:54`, returns counts only); adopting status+span return would give trace/debug artifacts locatable evidence ("exact at chars 4120-4187" vs "fuzzy, review") without changing the advisory gate contract.

- [HIGH] Fuzzy fallback uses a dual-gate LCS matcher: coverage >= 0.75 of extraction tokens AND density >= 1/3 matched-to-span ratio (`resolver.py:57-58`, `resolver.py:1377-1404`), with plural stemming via `lru_cache` (`resolver.py:1275-1281`). Evidence: PR #442 (https://github.com/google/langextract/pull/442) replaced a legacy difflib sliding-window aligner with this LCS DP after performance complaints (Issue #188).
  Impact: Our single `rapidfuzz.partial_ratio >= 0.90` floor against the entire document (`constants.py:50`, `grounding.py:51`) can accept quotes whose tokens are scattered across distant regions; LangExtract's density gate explicitly rejects that failure mode.

- [HIGH] The alignment subsystem is backed by 522 test functions across 28 files, including 37 resolver tests and 16 fuzzy-alignment case tests (`00-baseline.md:25`). Evidence: reproduced test count in baseline; v1.6.0 shipped 2026-07-02 with an alignment fix in the same burst (https://github.com/google/langextract/releases/tag/v1.6.0, https://github.com/google/langextract/commits/main/).
  Impact: These are not paper-thin unit tests on a toy aligner; the resolver (1213 LOC, `00-baseline.md:24`) has dedicated regression coverage for the exact mechanism we would port, reducing adoption risk versus inventing span alignment from scratch.

- [HIGH] Index-keyed ordered parallel collection (`gemini.py:487-504`: pre-sized `results[index]`, yield in input order despite `as_completed` completion) mirrors our existing `gather_concurrent` contract (`pipeline/runner.py:133-162`). Evidence: baseline DQ1 (`00-baseline.md:57`) and DQ4 (`00-baseline.md:66`).
  Impact: A per-tapetum bounded pool (opt-in via `default_concurrency`, `adjudicate.py:409`) could parallelize chunk triage without touching the global `Semaphore(1)` dissect relies on (`pipeline/tasks.py:38`); LangExtract proves the pattern at default `max_workers=10` (`gemini.py:129`) across 37K-star production use (https://github.com/google/langextract).

- [MED] Provider-pluggable entry-point registry (`pyproject.toml:94-97`) plus example-driven `ExampleData` few-shot schema (`core/data.py:261-270`) and v1.6.0 user `output_schema` for Gemini/OpenAI (https://github.com/google/langextract/releases/tag/v1.6.0) form a coherent extraction contract: instruct, exemplify, constrain output, then align. Evidence: OpenAI strict `response_format` built from examples (`providers/schemas/openai.py:178-188`).
  Impact: We already split provider abstraction (`ModelBackend`) from pipeline orchestration; LangExtract's pattern of deriving provider-native schemas from few-shot examples is a proven alternative to schema-in-prompt for cloud backends, and `output_schema` shows active API evolution we can study without importing the library.

- [MED] First-pass-wins overlap merge across sequential extraction passes (`annotation.py:46-84`) and streaming document emit cursor (`annotation.py:307-346`) are determinism-friendly orchestration primitives absent from our tapetum fold. Evidence: baseline comparison table (`00-baseline.md:49`).
  Impact: If tapetum ever runs multi-pass extraction (fast scan then deep fill-in), LangExtract's overlap resolution by `char_interval` is a ready-made, tested fold rule; our worst-axis merge (`adjudicate.py:171-246`) has no span-level dedup.

## False-pass hypothesis
A paraphrased evidence quote whose normalized tokens appear in three non-contiguous regions of a long WG21 paper (e.g., "constexpr evaluation" fragments in prose, a table cell, and a footnote) could score `partial_ratio >= 0.90` against the full markdown (`grounding.py:51`, `EVIDENCE_FUZZY_FLOOR=0.90` at `constants.py:50`) and pass as grounded even though no single contiguous span supports the quote; LangExtract's LCS density gate (`resolver.py:1388-1404`, `min_density=1/3`) would reject or downgrade that match.

## False-fail hypothesis
A valid LLM evidence quote that paraphrases source wording beyond the 0.75 token-coverage LCS threshold (`resolver.py:57`, `resolver.py:1400-1404`) receives `char_interval=None` and is treated as ungrounded, while our coarser `partial_ratio` floor (`0.90` vs document) might still accept the same quote; LangExtract trades higher false-negative rate on heavy paraphrase for lower false-positive rate on span locality.

## What would change my mind
A runtime A/B on 20+ real tapetum candidates showing that porting only the monotonic DP + dual-gate LCS into `ground_spans` (returning spans+status) does not reduce false-pass rate or improve inspect-report locatability versus our current 56-line implementation would flip this from "selectively adopt mechanisms" to "our coarse grounding is sufficient."
