# 18 - opendataloader-analyst

**Verdict:** usable-with-conditions (+ opendataloader-pdf/bench offer strong extraction-side page iteration and deterministic document QA patterns, but neither implements LLM-per-page verification; adopt bench null-eligibility, fail-closed partial_success, and triage page audit, not hybrid routing as a coverage guarantee)
**Confidence:** high

## Findings

- [CRITICAL] Hybrid extraction does NOT send every page to an LLM/VLM; auto-mode triages each page to JAVA (deterministic) or BACKEND (AI) and only full mode routes all pages to the backend. Evidence: `HybridDocumentProcessor.java:271-288` (full vs auto triage), `TriageProcessor.java:1105-1109` (per-page classify loop). Impact: opendataloader cannot be cited as prior art for "LLM saw every page"; it is selective extraction routing, analogous to whisker's capped escalation, not `--all-pages` review coverage.

- [HIGH] PDF processor iterates every physical page in local mode (parallel IntStream over `0..totalPages-1`) and hybrid mode (filter → triage → merge), with optional `--pages` subset via `getValidPageNumbers`. Evidence: `DocumentProcessor.java:210-243`, `298-314`, `505-507`; `HybridDocumentProcessor.java:509-522`, `1417-1439`; `MarkdownGenerator.java:97-108`. Impact: architectural "all pages touched" holds for extraction output assembly; useful for sidecar `page_count` audit in our mode, but says nothing about LLM verification depth per page.

- [HIGH] Per-page backend failure handling is explicit and fail-closed when fallback is off: `partial_success` failed pages collected (`HybridDocumentProcessor.java:717-725`), chunk IOException marks whole chunk failed (`764-773`), and `failFastIfBackendFailedWithoutFallback` throws listing 1-indexed pages (`483-496`); integration test locks the contract (`HybridBackendFailureIntegrationTest.java:42-48`, `:93-100`). Impact: direct template for our `--all-pages` fail-closed coverage check (required units vs `page_count`); copy the "list failed page numbers and abort" shape, not the default Java fallback that masks backend misses.

- [HIGH] Java-path per-page errors are swallowed: hybrid `processJavaPath` catches Exception, logs WARNING, and continues (`HybridDocumentProcessor.java:572-586`). Local parallel mode wraps any worker failure as document-level `IOException` (`DocumentProcessor.java:404-406`). Impact: anti-pattern for review mode; a silent empty page in hybrid Java lane would pass CLI exit 0 and corrupt golden review unless we add per-page non-empty / coverage assertions (which opendataloader bench also lacks).

- [HIGH] opendataloader-bench evaluation is fully deterministic and document-scoped: NID (rapidfuzz), TEDS/MHS (APTED), no LLM in the scoring loop. Evidence: `evaluator.py:103-105`, `evaluator_reading_order.py:37-38`, `evaluator_table.py:242-246`; README §3 (`README.md:58-60`). Aligns with field direction in `05-web.md` Q3/Q4 (olmOCR-Bench, ParseBench reject LLM-as-judge). Impact: bench is prior art for deterministic golden QA axes (whisker already ports NID/TEDS/MHS), not for exhaustive LLM judging.

- [MED] Bench has no per-page content verification guarantee: metrics compare whole-document markdown; null axes excluded from means when GT lacks tables/headings (`evaluator_table.py:234-235`, `evaluator_heading_level.py:138-139`, `evaluator.py:112-113`, `128-163`); eval exceptions skip a doc and continue (`evaluator.py:237-239`). Corpus regression gates means only (`run.py:53-117`, `thresholds.json:1-9`). Impact: a single dropped page can hide inside a good doc-level NID; confirms 00-baseline worst-page-wins concern applies to structural metrics too unless we add mandatory per-page units.

- [MED] The only page-scoped bench metric is triage routing accuracy (hybrid engines): compares per-page JAVA/BACKEND decisions against GT table presence (`evaluator_triage.py:97-139`, `run.py:252-261`; thresholds `triage_recall`/`triage_fn_max` in `thresholds.json:8-9`). Impact: adoptable as a sidecar audit ("was this page routed to deep processing?") but measures routing correctness, not candidate-markdown fidelity; orthogonal to golden-review verification.

- [LOW] CLI batch semantics differ by input source: invalid PDF from directory traversal is WARNING+skip (exit 0), CLI argument is error+fail (`CLIMain.java:209-235`). Impact: irrelevant to single-paper review mode but shows their coverage accounting is file-granular, not page-granular with completion certificates.

## False-pass hypothesis

A 15-page WG21 paper loses page 8 entirely from the candidate markdown (empty hybrid Java lane after swallowed exception at `HybridDocumentProcessor.java:583-586`). Document-level NID on the remaining text stays above threshold, bench `check_regression` passes on corpus means, and no triage.json exists for non-hybrid runs — operator believes full coverage when 1/15 pages was never validated.

## False-fail hypothesis

Hybrid `--hybrid-fallback` disabled, backend returns `partial_success` for one table-heavy page (`HybridDocumentProcessor.java:351-354`). Entire document aborts with `IOException` listing that page even though the Java path would produce an acceptable (lower table fidelity) markdown for the other 14 pages — correct for extraction fidelity, harsh for advisory golden review if we copied fail-fast without human triage.

## What would change my mind

Discovery of a per-page mandatory baseline in opendataloader-bench (analogous to olmOCR `BaselineTest` per page in `05-web.md` Q3) — e.g. evaluator loops pages and fails if any page's extracted segment is empty or below a floor — would upgrade verdict to **usable** for structural verification coverage without LLM.
