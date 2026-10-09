# 07 - langextract-grounding

**Verdict:** usable-with-conditions — langextract's three-tier char-interval aligner is the strongest open-source grounding reference we surveyed, but tapetum already ports its safe core (monotonic exact DP, `char_interval=None` reject, post-alignment guard); what remains portable is persistence/inspect shape and optional stemming, not LCS fuzzy or schema-retry, and it offers no numeric score-fusion model for merged det+LLM lanes.
**Confidence:** high

## Findings

- [CRITICAL] Three-tier grounding turns LLM extraction strings into verifiable `char_interval` spans with graded `AlignmentStatus`, rejecting unlocatable claims via `char_interval=None`. Evidence: Tier 1 monotonic exact DP (`resolver.py:948-959`, `1113-1243`), Tier 2 difflib exact/lesser (`resolver.py:962-1019`), Tier 3 LCS fuzzy fallback (`resolver.py:1027-1065`, `760-787`); `Extraction.char_interval` is `None` when alignment fails (`core/data.py:74-76`, `87-88`); README documents consumer filter `[e for e in result.extractions if e.char_interval]` (`README.md:94`). Impact: validates Goal 1 (keep LLM lane) by showing deterministic post-hoc verification is the right pattern; tapetum already borrows the reject idea and has gone further with a post-alignment guard (`grounding.py:220-227`) langextract lacks.

- [CRITICAL] LCS fuzzy dual-gate (coverage ≥0.75 AND density ≥1/3) is deliberately unsafe to port: it codifies gapped wrong-span acceptance. Evidence: `_FUZZY_ALIGNMENT_MIN_THRESHOLD = 0.75`, `_FUZZY_ALIGNMENT_MIN_DENSITY = 1/3` (`resolver.py:57-58`); `_accept_lcs_match` gates (`resolver.py:1377-1404`); oracle test expects 9-token noise span for 3-token extraction (`tests/fuzzy_alignment_cases_test.py:213-222`). Impact: confirms tapetum's decision to keep document-level `partial_ratio ≥ EVIDENCE_FUZZY_FLOOR` (0.90, baseline C1 lane `constants.py:50`) instead of LCS; a merged score must not treat langextract `MATCH_FUZZY` spans as high-trust evidence.

- [HIGH] No per-document extraction-quality score or det+LLM fusion exists; grounding is boolean-ish per item, not aggregated. Evidence: aligner logs `exact_matches`/`lesser_matches` counts at debug only (`resolver.py:941-943`, `1067-1072`); `ScoredOutput(score=1.0, ...)` is a provider placeholder, not alignment quality (`providers/gemini.py:371`); no module computes document-level coverage. Impact: for Goal 3 (merged score), langextract cannot be copied as a fusion formula; the adoptable derivative is a computed `grounding_rate = grounded_quotes / cited_quotes` adjunct to tapetum `confidence`, not a replacement for whisker `ref_overall` or tapetum verdict.

- [HIGH] Persistence model is one JSONL row per document with full extraction objects including `char_interval` and `alignment_status`. Evidence: `save_annotated_documents` writes `json.dumps(data_lib.annotated_document_to_dict(adoc))` per line (`io.py:85-130`); `annotated_document_to_dict` serializes enums and nested intervals (`data_lib.py:57-82`); README shows `.jsonl` → interactive HTML viz (`README.md:127-131`). Impact: directly serves Goal 2 (persist both lanes): whisker could extend `<pid>.whisker.json` or unify sidecars with a `grounded_evidence[]` block mirroring langextract's per-span `{quote, status, start, end}` — tapetum already does this in `<pid>.whisker.tapetum.json` (`models.py:128-131`, baseline §2).

- [HIGH] Schema-constrained decoding has no validation-retry loop; parse failures drop silently by default. Evidence: `resolver.py:309-321` (`suppress_parse_errors` returns `[]`); `extract()` forces `suppress_parse_errors=True` via `alignment_kwargs.setdefault` (`extraction.py:365`); Gemini retries only transient HTTP (`gemini.py:351-391`, `_RETRYABLE_API_CODES` at `gemini.py:49`); OpenAI strict `json_schema` is cloud-only (`providers/schemas/openai.py:178-188`). Impact: langextract's schema path is weaker than our `VllmThinkingBackend` raw-JSON retry (baseline §2, 6 tapetum errors from truncated JSON); do not adopt for Goal 1, keep our D6/D10 retry stack.

- [MED] Plural stemming (`_normalize_token`, `lru_cache(maxsize=10000)`) is a low-cost false-negative fix tapetum's exact tier still lacks. Evidence: `resolver.py:1275-1281`; applied before LCS/legacy fuzzy (`resolver.py:1034-1037`). Impact: `"tables"` vs `"table"` evidence quotes may fail tapetum exact substring (`grounding.py:229`) until fuzzy ratio saves them; ~7 LOC port, must align with `normalized_text` rules (`metrics.py:338-340`) to avoid double-normalization.

- [MED] `prompt_validation.py` pre-flights few-shot examples through the same aligner, classifying `IssueKind.FAILED` (`char_interval=None`) vs `NON_EXACT` (`MATCH_FUZZY`/`MATCH_LESSER`) (`prompt_validation.py:56-60`, `180-218`). Impact: no analogue in tapetum prompt QA today; portable as an offline lint for `tapetum_llm.md` worked examples before batch runs, improving Goal 1 fidelity without touching CI gate (C1).

- [LOW] Visualization consumes JSONL and renders char-position highlights with `startPos`/`endPos` per extraction (`visualization.py:401-412`, `431-446`). Impact: pattern for enriching `tapetum-inspect.md` or a future HTML inspect artifact (Goal 2 reporting); not required for merge math.

## False-pass hypothesis

Model cites `"metformin hydrochloride tablet"` against a gapped clinical source; langextract LCS returns `MATCH_FUZZY` with `char_interval` covering mostly unrelated tokens (`fuzzy_alignment_cases_test.py:213-222`, `resolver.py:1377-1404`). A merged det+LLM score that counts any non-`None` `char_interval` as grounded evidence would falsely certify the quote's location; tapetum's post-alignment guard blocks this for exact tier but fuzzy tier still accepts via `partial_ratio` without a localized span (`grounding.py:231-236`).

## False-fail hypothesis

Model outputs overlapping entities `"Naprosyn"` and `"arthritis"` from one sentence; monotonic DP aligns `"arthritis"` first and leaves `"Naprosyn"` at `char_interval=None` (`resolver_test.py:1024-1057`, `resolver.py:1113-1185`). Whisker/tapetum substring grounding keeps both (`grounding.py:229`); a merge rule that penalizes tapetum when langextract-style overlap policy would drop a quote would falsely fail papers with nested valid citations.

## What would change my mind

A langextract release (or our fork) shipping PR #480 CJK char-substring fallback plus a default post-alignment span-text guard (like tapetum `grounding.py:220-227`) on all tiers, with published wrong-span rate <1% on a WG21-representative corpus and a documented document-level `grounding_rate` metric wired into JSONL output — would flip to **usable** as a full three-tier reference for Goals 2-3.
