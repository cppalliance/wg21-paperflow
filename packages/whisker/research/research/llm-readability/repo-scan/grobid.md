# Repo scan: GROBID (kermitt2/grobid)

**Does it verify LLM-readability?** **partial** (field-level fact recovery against gold XML is RealDocBench-shaped, but no LLM reader, no markdown-output comprehension gate, and maintainers explicitly disclaim absolute consumability scoring)

Scanned: local shallow clone at `packages/whisker/research/repos/grobid` (read-only, 2026-07-06).

## Findings

### End-to-end eval is schema field recovery, not LLM comprehension

`EndToEndEvaluation.java` compares GROBID TEI output to publisher gold XML (NLM/JATS or Pub2TEI TEI) via XPath-defined fields (`FieldSpecification.java:36-80` title/authors/abstract paths). Four parallel string matchers score each textual field: strict, soft (punctuation/case/space stripped), relative Levenshtein ≥ 0.8, Ratcliff/Obershelp ≥ 0.95 (`EndToEndEvaluation.java:453-461`, `:66-67`, `:1121-1170`). Numeric/date fields skip fuzzy tiers (`EndToEndEvaluation.java:460-461`).

This is **comprehension-adjacent**: recovering typed facts (title, first author, DOI, abstract snippet) from noisy PDF input resembles RealDocBench's field-level QA track (05-web Q3). It is **not LLM-readability verification**: no markdown is scored, no LLM reads output, and matching is deterministic string tiers over extracted slots, not semantic question answering.

### Instance-level "all fields correct" is the closest comprehension proxy

Per citation/header instance, all constituent fields must pass the active tier for the instance to count correct (`EndToEndEvaluation.java:1174-1185`). Published PMC benchmarks report instance-level recall separately from field micro-F1 (`doc/benchmarks/Benchmarking-pmc.md:98-110`: 205/1943 strict instances vs 93.54% field micro-F1 under Levenshtein). That catches partial extractions a single scalar would miss, but still tests **structured slot alignment**, not "can an LLM answer questions from this text."

### Maintainers disclaim absolute downstream usability

`doc/End-to-end-evaluation.md:187` states evaluation "cannot be considered currently as a reliable absolute evaluation (how good GROBID will extract valid and usable structures from PDF), but rather as a way to keep track of progress from one version of GROBID to another." Gold XML imperfections (raw-string citations, interval callout gaps) inject false positives/negatives (`:134-170`). This contradicts treating GROBID scores as LLM-consumability proof.

### LLM mentioned only as optional downstream consumer; never verified

Docs describe optional client-side Markdown/JSON projection "for feeding an LLM" (`doc/Grobid-service.md:137-140`, `doc/Frequently-asked-questions.md:278`). The server always returns TEI; converters are lossy and live outside this repo. **No test, benchmark, or metric in grobid/grobid-trainer verifies that Markdown/JSON is LLM-readable.** External olmOCR paper downstream-pretraining comparison (Grobid tokens vs olmOCR-linearized tokens, 05-web Q3) is not implemented in this codebase.

### No LLM-as-judge, fact assertions, or comprehension corpus

Repo search finds zero references to olmOCR-bench, fact assertions, LLM-as-judge, or comprehension QA. Eval engine tests cover token/field stats for sequence-labelling models (`EvaluationUtilitiesTest.java:13-70`), not end-to-end consumability.

### CI gates unit tests only; end-to-end eval is manual release ritual

`ci-build-unstable.yml:31-32` runs `./gradlew assemble test` only. `jatsEval`/`teiEval` Gradle tasks exist (`build.gradle:631-658`) but are not in CI. Eval Docker image build is `workflow_dispatch` only (`ci-build-manual-eval.yml:3-5`). Benchmark numbers are committed markdown snapshots refreshed manually (`doc/End-to-end-evaluation.md:78-88`, `doc/benchmarks/Benchmarking.md:13-15`).

### Normalization, stratification, and corpus-specific field nulling (structural QA strength)

Pre-compare normalization: `basicNormalization` lowercases, collapses whitespace, unescapes entities (`EndToEndEvaluation.java:2090-2096`); fulltext adds Unicode normalize (`:2122-2145`). Section strata HEADER / CITATION / FULLTEXT (`:60-62`, `:488-497`). Corpus-specific field drops (PMC strips doi/pmid/pmcid from citation eval `:505-508`; eLife drops keywords `:510-512`). Micro/macro P/R/F1 with support counts (`Stats.java:232-278`, `Benchmarking-pmc.md:42-51`).

## Portable to whisker (ranked)

1. **Multi-tier text regression** — adopt GROBID relative Levenshtein pass `(max_len - dist) / max_len >= 0.8` after normalization as a secondary guard tier beneath strict axis slack (`EndToEndEvaluation.java:1126-1134`, `:66`). Directly maps to whisker `nid` on normalized markdown.
2. **Corpus-specific axis nulling** — skip axes when N/A per paper (PMC-style field drops `:505-527` → whisker `"teds": null` for table-less papers).
3. **Normalization-before-compare contract** — document and version the normalization pipeline used at baseline write time (`:2090-2159`; whisker `normalized_text` path).
4. **Per-field / sub-axis breakdown in guard findings** — keep four CI axes but surface localized collapse (title vs table) like GROBID field rows (`FieldSpecification.java`, `Benchmarking-pmc.md:42-48`).
5. **Instance-level strict mode (optional)** — fail a PID only when all verified facts pass, mirroring instance-level recall (`Benchmarking-pmc.md:98-110`).
6. **Committed human-readable benchmark snapshots** — markdown tables alongside JSON baseline for PR review (`doc/benchmarks/Benchmarking-pmc.md`, `Benchmarking.md:13-15`).
7. **Support counts in reports** — expose GT table/block counts so small-sample swings are visible (`Benchmarking-pmc.md:42-48` support column).
8. **Subsample smoke eval** — `fileRatio` partial corpus (`EndToEndEvaluation.java:64`, `:569-573`) for fast guard smoke; low priority for whisker's small corpus.

**Not portable as comprehension:** GROBID's XPath field specs target TEI/XML slots; whisker Lane 3 needs human-verified facts on markdown, not automatic gold XML alignment.

## Cross-check vs redteam report

**Confirms** (`packages/whisker/research/redteam/grobid.md`):

- Committed benchmark snapshots, manual refresh, no CI `jatsEval`/`teiEval` (`ci-build-unstable.yml:31-32`, `build.gradle:631-640`, `Benchmarking.md:13-15`).
- Four matching tiers with fixed Levenshtein 0.8 / Ratcliff 0.95 (`EndToEndEvaluation.java:66-67`, `:453-461`).
- Per-field micro/macro P/R/F1, section strata, instance-level counts, corpus field nulling (`Stats.java:232-278`, `:505-527`, `Benchmarking-pmc.md:98-110`).
- Top portable detail (Levenshtein secondary tier) remains highest-value adoption.

**Adds / nuance (this scan's LLM-readability lens):**

- Redteam framed GROBID purely as regression-gate vs whisker guard. **Honest comprehension assessment:** field-level P/R/F1 **is** RealDocBench-shaped fact recovery, but over TEI/XML with deterministic string tiers, not LLM-read markdown comprehension. Closer to whisker Lane 2 fidelity + typed field checks than Lane 3 or olmOCR-bench.
- Redteam did not note GROBID's explicit disclaimer against absolute usability scoring (`End-to-end-evaluation.md:187`), which undercuts any claim that GROBID eval proves LLM-readability.
- Redteam did not note LLM is documented only as optional lossy Markdown downstream (`Grobid-service.md:137-140`) with zero in-repo verification.
- No contradiction found on regression-gate mechanics; all cited line references verified in shallow clone.
