# langextract — LLM-readability repo scan

**Source:** `packages/whisker/research/repos/langextract` (google/langextract, shallow clone read 2026-07-06). Prior persona synthesis at `packages/whisker/research/langextract/SYNTHESIS.md` skimmed; grounding mechanism re-verified here, synthesis findings not re-filed.

**Redteam report:** none (`packages/whisker/research/redteam/` has no `langextract.md`).

**Does it verify LLM-readability?** **partial**

langextract is **not** a document-to-markdown converter. It uses LLMs to extract structured spans from unstructured source text and verifies that each extraction **grounds to exact source character offsets** (verbatim alignment). That is **provenance / hallucination control** for extractions, not "can a downstream LLM comprehend converted markdown." It partially overlaps whisker needs via `tapetum_llm/grounding.py`, but does not implement comprehension facts, table-neighbor checks, or olmOCR-style QA on converted papers.

---

## Findings

1. **[HIGH] Three-tier deterministic aligner (core verification mechanism).** Post-LLM, every extraction is aligned to source text without a second model:
   - **Tier 1:** monotonic exact-occurrence DP (`resolver.py:1113-1243`, `_select_monotonic_matches` at `:1113-1185`, `_apply_monotonic_exact_matches` at `:1188-1243`) — repeated phrases map to successive non-overlapping occurrences; sets `char_interval` + `AlignmentStatus.MATCH_EXACT` (`:1237-1241`).
   - **Tier 2:** difflib `SequenceMatcher` blocks for lesser exact matches (`:962-1019`, status `MATCH_LESSER` at `:1005-1018`).
   - **Tier 3:** LCS-DP fuzzy fallback with coverage + density gates (`:717-787`, `_accept_lcs_match` at `:1377-1404`: `_FUZZY_ALIGNMENT_MIN_THRESHOLD = 0.75`, `_FUZZY_ALIGNMENT_MIN_DENSITY = 1/3` at `:57-58`).

   Impact: this is **span-level fact grounding**, not document comprehension. Directly comparable to tapetum evidence verification.

2. **[HIGH] Graded `AlignmentStatus` + `CharInterval` as the pass/fail surface.** Enum at `core/data.py:43-47` (`MATCH_EXACT`, `MATCH_GREATER`, `MATCH_LESSER`, `MATCH_FUZZY`). Extractions without resolvable `char_interval` are effectively ungrounded. README positions "Precise Source Grounding" as core value (`README.md:39`).

3. **[HIGH] Oracle unit tests pin expected offsets (deterministic QA, not LLM-judge).** `tests/resolver_test.py:1585-1644` parametrizes extractions with expected `char_interval`, `token_interval`, `alignment_status` (e.g. fuzzy fail leaves `char_interval=None` at `:1615-1616`). `tests/fuzzy_alignment_cases_test.py:212-222` plants gapped source and expects a specific `char_interval` for LCS — documents Tier 3 accepting gapped spans at density floor.

4. **[CRITICAL] Tier 3 LCS can ground wrong localized spans.** `_accept_lcs_match` passes when `matches >= ceil(len*0.75)` and `matches/span_len >= 1/3` (`resolver.py:1400-1404`). Oracle test codifies a 9-token gapped span for a 3-token extraction (`fuzzy_alignment_cases_test.py:213-222`). Impact: **do not port Tier 3 thresholds** to tapetum; keep whisker `EVIDENCE_FUZZY_FLOOR = 0.90` document-level `partial_ratio`.

5. **[MED] Ad-hoc benchmark suite measures grounding rate, not comprehension.** `benchmarks/benchmark.py:222-260` counts entities with non-null `char_interval` vs ungrounded after a live LLM `extract()` call — no gold labels, no pass/fail gate in CI. `benchmarks/fuzzy_benchmark.py:16-27` benchmarks alignment wall-time/correctness on synthetic sizes. Tokenization throughput only elsewhere (`benchmark.py:94-138`). Impact: operational telemetry, not LLM-readability certification.

6. **[MED] Fail-soft defaults (anti-pattern for whisker fidelity).** `extract()` defaults `suppress_parse_errors=True` (`extraction.py:365`); parse/schema failures return `[]` silently (`resolver.py:309-321`). Impact: opposite of whisker "fail, never partial"; not portable.

7. **[LOW] No markdown conversion / downstream consumability path.** Library consumes raw text; no table-neighbor facts, math surface, reading-order assertions, or olmOCR-bench analogue. Web Q3 benchmarks (ParseBench, RealDocBench) are out of scope for this repo.

---

## Comparison to tapetum_llm `grounding.py`

| Aspect | langextract | whisker `grounding.py` |
|--------|-------------|------------------------|
| Exact match | Token DP + difflib; returns `char_interval` | Normalized substring `in` test; first occurrence only (`grounding.py:49`) |
| Fuzzy | LCS subsequence + 0.75/0.333 density | `partial_ratio >= 0.90` over full document (`:51`, `constants.py:50`) |
| Repeated quotes | Monotonic DP disambiguates successive hits | Always first substring hit |
| Return shape | `char_interval`, `AlignmentStatus` | kept/dropped count only (`:34-35`) |
| LLM in loop | Yes (extraction); alignment deterministic | No LLM in grounding |

Prior synthesis (`langextract/SYNTHESIS.md`) and persona 20 agree: **port Tier 1 + span return; reject Tier 3 and library dependency.**

---

## Portable to whisker (ranked)

| Rank | Adopt | Evidence | Action |
|------|-------|----------|--------|
| 1 | **Monotonic exact-occurrence DP** | `resolver.py:1113-1243` | Re-implement ~150 LOC in `tapetum_llm/grounding.py`; map repeated evidence quotes to successive non-overlapping positions in model output order |
| 2 | **Return `(quote, char_interval, AlignmentStatus)`** | `core/data.py:43-47`, `resolver.py:1237-1241` | Extend `ground_spans` for `--inspect` locatability |
| 3 | **Post-alignment substring guard** | Tier 3 CRITICAL above | After any exact span, reject if `markdown[char_interval]` != quote after normalization |
| 4 | **Optional plural stem before exact pass** | `resolver.py:1275-1281` | ~7 LOC; align with `normalized_text` rules |
| 5 | **Keep whisker 0.90 partial_ratio as fuzzy tier** | vs `:57-58` | Do **not** import 0.75/0.333 LCS gates |

Do not adopt: langextract as dependency (cloud SDKs, fail-soft defaults), full three-tier resolver, LCS fuzzy tier, `benchmarks/benchmark.py` grounding-rate metric as a CI gate.

---

## Cross-check vs redteam report

**No redteam report exists** for langextract. This scan is the primary repo-level record for the LLM-readability wave.

Cross-check against prior **`packages/whisker/research/langextract/SYNTHESIS.md`** (not redteam):

| synthesis claim | Scan verdict | Evidence |
|-----------------|--------------|----------|
| Three-tier aligner at stated line ranges | **CONFIRMED** | `resolver.py:948-959`, `:1113-1243`, `:1287-1363` |
| Tier 3 density-floor wrong-span oracle | **CONFIRMED** | `fuzzy_alignment_cases_test.py:213-222`, `resolver.py:1403-1404` |
| `ground_spans` occurrence-blind | **CONFIRMED** | `grounding.py:49` (no offset return) |
| adopt-partially: port DP only | **CONFIRMED** | aligns with findings above |

No contradictions with prior langextract research; this scan narrows scope to **grounding-as-verification** (partial LLM-readability via span provenance) vs **comprehension QA** (whisker Lane 3 / olmOCR-bench).
