# C20 — PDF/HTML Source-Aware Audit

**Auditor**: PDF/HTML Source-Aware Auditor
**Focus**: D4 (source-type routing, lane parity)
**Scope**: `packages/whisker/src/whisker/tapetum_llm/pdf_judge.py`, `textlayer.py`, `html_outline.py`, `adjudicate.py`, `source_router.py`
**Date**: 2026-07-19

---

## Executive Summary

PDF and HTML papers follow independent paths through the advisory lane. PDF papers go through PyMuPDF text extraction → monolith judge → per-page screen → scoped escalation → unit checks. HTML papers go through the markdown text cascade (triage → adjudicate → decide) plus source-aware section routing and unit checks. Both lanes are independent of whisker deterministic signals (no sidecar reading in prompts). The `screen_pages` function is purely deterministic with `content_recall` per page. Metadata/outline checks are mandatory for both lanes.

---

## Findings

### F1. PDF lane: PyMuPDF text extraction, structured PdfJudgment

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | The PDF lane extracts text via PyMuPDF's `page.get_text("text", sort=True)` (sorted by vertical-then-horizontal position for reading order). Output is a structured `PdfJudgment` Pydantic model with `verdict`, `missing_content` (capped at `MAX_MISSING_QUOTES` = 5), `confidence`, and `reasoning`. |
| **Evidence** | `textlayer.py:104-157` (`extract_textlayer`: uses `pymupdf.open`, `page.get_text("text", sort=True)`). `pdf_judge.py:266-283` (`PdfJudgment` schema: `verdict: Verdict`, `missing_content: list[str]`, `confidence: float`, `reasoning: str`). `pdf_judge.py:637-644` (monolith call: `judgment: PdfJudgment = await run_judge_task(agent, system, user_msg, PdfJudgment, ...)`). |
| **Affected gate** | D4 (source provenance) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F2. HTML papers go through text cascade (not PDF judge)

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | The CLI determines source kind from the file extension. HTML papers (`.html`/`.htm`) go through `adjudicate_paper` (the text cascade). PDF papers go through `judge_pdf_extraction`. The `--text-only` flag forces all papers through the text lane. |
| **Evidence** | `cli.py:531-543` (`_source_kind`: checks `suffix.lower()` for `.pdf` or `.html`/`.htm`). `cli.py:932-934` (`use_pdf_judge = kind == "pdf" and judge_agent is not None`). `cli.py:973-1031` (PDF path: `judge_pdf_extraction`), `cli.py:1032-1066` (text path: `adjudicate_paper`). `cli.py:265-269` (`--text-only` flag). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | A paper with `unknown` source kind (e.g., `.docx`) falls through to the text lane, which may not be appropriate. This is documented as a fallback. |
| **False-fail hypothesis** | N/A. |

### F3. Both lanes are independent of whisker deterministic signals

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | Neither the PDF judge prompts nor the text cascade prompts inject whisker verdicts, flags, or metrics. The text-lane triage message builder (`_build_triage_message`) explicitly documents: "Independence: no deterministic-lane signals (verdict, flags, metrics) are injected." The PDF judge receives only the raw text layer and converted markdown. `screen_pages` is lane-local, computed from source pages and candidate markdown only. |
| **Evidence** | `adjudicate.py:544-550` (docstring: "Independence: no deterministic-lane signals (verdict, flags, metrics) are injected"). `adjudicate.py:593` (adjudicate message: "Independence: no deterministic-lane signals (verdict, flags) are injected"). `pdf_judge.py:318-319` (`screen_pages` docstring: "never reads the deterministic whisker sidecar (lane independence)"). `source_router.py:8-11` (docstring: "never reads deterministic whisker artifacts"). Tests: `test_source_aware_integration.py:252-268` (`TestLaneIndependence`). |
| **Affected gate** | D4 (confirmation-bias defense) |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | The text lane reads the whisker sidecar in `_custom_select` (line 218-225), but it is stored in `state.whisker_signals` and only used for the `whisker_verdict` field in the result, never injected into any prompt. |
| **False-fail hypothesis** | N/A. |

### F4. Per-page screen: `screen_pages()` with content_recall per page

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `screen_pages` computes a deterministic `content_recall(tomd_md, dehyphenated_page)` for each page. Pages with fewer than `PAGE_MIN_TOKENS` (50) tokens are skipped as trivial. Pages below `PAGE_RECALL_FLOOR` (0.90) are flagged. The function has no LLM, no agent, no backend parameter. Cross-page-style hyphenation is rejoined before token counting. |
| **Evidence** | `pdf_judge.py:310-335` (`screen_pages` function). `pdf_judge.py:119-131` (`_dehyphenate` function). `pdf_judge.py:323` (`dehyphenated = _dehyphenate(page_text)`). `constants.py:159` (`PAGE_RECALL_FLOOR = 0.90`). `constants.py:165` (`PAGE_MIN_TOKENS = 50`). Tests: `test_pdf_judge.py:1037-1101` (missing page flagged, trivial page skipped, min-tokens boundary, dehyphenation prevents false flag, dehyphenation is load-bearing, 1-indexed pages, signature has no agent/backend). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F5. Text layer normalization: header/footer stripping, page number removal

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `clean_pages` strips running headers/footers (lines repeated on >= 30% of pages, < 120 chars), isolated page numbers, and preserves blank lines per page. `normalize_textlayer` joins cleaned pages and collapses 3+ consecutive newlines. Header/footer detection requires >= 3 pages (`_MIN_PAGES_FOR_HEADER_DETECTION`). |
| **Evidence** | `textlayer.py:283-338` (`clean_pages`). `textlayer.py:341-355` (`normalize_textlayer`). `textlayer.py:62` (`HEADER_FOOTER_FREQ_THRESHOLD = 0.30`). `textlayer.py:65-66` (`_MIN_PAGES_FOR_HEADER_DETECTION = 3`). `textlayer.py:69` (`_ISOLATED_PAGE_NUMBER_RE`). Tests: `test_pdf_judge.py:145-317` (extensive normalization, header removal, page number removal, short doc quirk, whitespace collapsing, clean_pages regression baselines). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F6. HTML outline extraction: stdlib html.parser, no external dependency

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `html_outline.py` extracts h1-h6 headings and heading-bounded sections from HTML source using stdlib `html.parser.HTMLParser`. No lxml or beautifulsoup dependency. Section units include text, code-block count, table/image presence, and content-token count. |
| **Evidence** | `html_outline.py:21` (`from html.parser import HTMLParser`). `html_outline.py:57-91` (`_HeadingExtractor` class). `html_outline.py:94-184` (`_SectionExtractor` class). `html_outline.py:43-55` (`SectionUnit` dataclass). Tests: `test_html_outline.py:1-82` (basic headings, empty, nested tags, whitespace, all levels, section extraction, code block counting). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | The parser handles `<pre>` as code blocks but not `<code>` alone (only when nested in `<pre>`). This matches the semantics: standalone `<code>` is inline code, not a code block. |
| **False-fail hypothesis** | N/A. |

### F7. Source-aware routing: PDF pages and HTML sections routed independently

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `route_pdf_units` identifies risky PDF pages via: (1) per-page recall below `PAGE_RECALL_FLOOR`, (2) C++ keyword token delta exceeding `TOKEN_DELTA_THRESHOLD` (5), (3) missing captions, (4) heading drift (large-font source lines not found as markdown headings). `route_html_units` identifies risky HTML sections via: (1) heading-level drift (source tag vs candidate heading level), (2) per-section recall below `SECTION_RECALL_FLOOR` (0.90), (3) missing code blocks. TOC sections are skipped by both routers. |
| **Evidence** | `source_router.py:149-233` (`route_pdf_units`: recall, token delta, captions, heading drift). `source_router.py:236-316` (`route_html_units`: heading drift, section recall, code block delta). `source_router.py:145-146` (`_is_sanctioned_toc_title`). `constants.py:193-211` (`SECTION_RECALL_FLOOR`, `SECTION_MIN_TOKENS`, `TOKEN_DELTA_THRESHOLD`, `MAX_UNIT_CHECKS`). Tests: `test_source_router.py:83-306` (low recall, token delta, document-wide delta, missing caption, heading drift, clean passes, TOC immunity, duplicate heading occurrence matching, code block counting). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | Token delta uses document-wide keyword counts, not per-page. A keyword removed from page A but added on page B would show delta=0 (false negative). This is accepted as document-level is the right scope for keyword qualifiers like `constexpr`. |
| **False-fail hypothesis** | N/A. |

### F8. Metadata/outline check is mandatory for both lanes

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | Both the PDF lane and the HTML text-lane run a mandatory `run_metadata_outline_check` comparing source front-matter and heading outline against the candidate. A metadata fail forces the overall verdict to fail. A metadata review demotes a pass to review. |
| **Evidence** | `pdf_judge.py:663-674` (PDF lane: `metadata_check = await run_metadata_outline_check(...)`). `pdf_judge.py:697-700` (metadata verdict folds into overall: `if metadata_check.verdict == "fail": verdict = "fail"`). `adjudicate.py:456-489` (`_run_html_unit_checks`: `state.metadata_outline_check = await run_metadata_outline_check(...)`). `adjudicate.py:354-361` (metadata verdict folds into text-lane decide). `unit_judge.py:134-170` (`run_metadata_outline_check` implementation). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | None. |
| **False-fail hypothesis** | N/A. |

### F9. PageUnit structured extraction: font-based heading detection, table detection

| Field | Value |
|---|---|
| **Severity** | INFO |
| **Claim** | `extract_page_units` uses PyMuPDF's blocks API to extract per-page structured metadata: heading candidates (lines with font size > 1.2x median), caption lines (`Figure N`/`Table N`), image blocks, tabular structure (multi-column text blocks), and C++ keyword counts. This enriches the source-router's risk signals beyond raw text. |
| **Evidence** | `textlayer.py:173-280` (`extract_page_units`). `textlayer.py:246-249` (heading candidates: `size > median_size * _HEADING_FONT_MULTIPLIER`). `textlayer.py:241-243` (caption lines: `_CAPTION_RE`). `textlayer.py:160-170` (`_block_looks_tabular`: multi-column rows). Tests: `test_source_router.py:31-60` (`test_pdf_page_units_from_simple_pdf`: real PDF creation, heading detection, caption lines, table detection, code token count). |
| **Affected gate** | D4 |
| **Confidence** | 1.00 |
| **False-pass hypothesis** | Font-based heading detection depends on a stable median font size. A document with uniformly large or small fonts would have no heading candidates. |
| **False-fail hypothesis** | N/A. |

---

## Summary Verdict

PDF and HTML lanes are structurally independent with clear source-type routing. The PDF lane uses PyMuPDF for text extraction with per-page recall screens and structured page-unit metadata. The HTML lane uses stdlib `html.parser` for outline extraction with section-level routing. Both lanes enforce lane independence (no deterministic sidecar in prompts) and mandatory metadata/outline checks. The per-page screen is purely deterministic with calibrated thresholds. **No blocking issues. D4 compliance is comprehensive with strong parity between lanes.**
