# 22 - Headers/Footers/TOC

**Verdict:** usable-with-conditions — Marker v2 strips running page headers/footers (and typical page-number chrome) by default via layout labels plus two heuristic backstops, but it does **not** strip in-document `TableOfContents` blocks; those are detected, table-processed, and emitted into markdown, which fails whisker's `no_toc_leak` contract that tomd enforces by stripping TOC.
**Confidence:** high

Clone: `packages/whisker/research/repos/marker-v2.0.0/` @ `947d768` (Marker 2.0.0). Comparison anchors: tomd TOC/furniture strip (`packages/tomd/src/tomd/api.py`, `lib/pdf/cleanup.py`, `lib/toc.py`) and whisker `gates.py` `no_toc_leak`.

## Findings

- [HIGH] **PageHeader/PageFooter are layout-classified then suppressed from HTML/markdown by default.** Evidence: Surya label map wires `"PageHeader"`/`"PageFooter"` → `BlockTypes` (`marker/schema/labels.py:10-11`); block classes default `ignore_for_output: bool = True` (`pageheader.py:11`, `pagefooter.py:11`); `Block.assemble_html` returns `""` when that flag is set (`base.py:250-251`). Opt-in restore: `keep_pageheader_in_output` / `keep_pagefooter_in_output` flip the flag in `assemble_html` (`pageheader.py:15-16`, `pagefooter.py:15-16`) and are documented as "removed by default" (`README.md:131`). Impact: furniture strip is a first-class product feature, not an accident of OCR skip.

- [HIGH] **Two heuristic backstops catch furniture the layout model misses.** Evidence: (1) `IgnoreTextProcessor` scans first/last text-like blocks per page, strips leading/trailing digits (`ignoretext.py:66-70`), and marks fuzzy-common elements `ignore_for_output` when frequency ≥20% of pages or streak ≥3 and count >3 (`ignoretext.py:23-42`, `72-95`); docstring names "headers, footers, or page numbers" (`ignoretext.py:14-17`). (2) `MarginaliaProcessor` relabels short edge blocks in the top 8%/bottom 13% zones that sit outside body text (`marginalia.py:13-37`, `95-106`). Both sit in `PdfConverter.default_processors` after `DocumentTOCProcessor` (`pdf.py:87-94`). Impact: page-number chrome often dies either as `PageFooter` or as digit-stripped repeating edge text; not a dedicated "page number" block type.

- [MED] **`PageHeaderProcessor` does not strip; it only reorders.** Evidence: moves `PageHeader` ids to the front of `page.structure` (`page_header.py:7-22`). Strip still happens at render time via `ignore_for_output`. Impact: easy to misread as a stripper; the real deletion is the block default + heuristics + `assemble_html` empty return.

- [HIGH] **In-document TOC is detected and kept, not stripped.** Evidence: `BlockTypes.TableOfContents` exists (`schema/__init__.py:28`); Surya maps `"TableOfContents"` (`labels.py:23`); class `TableOfContents(BaseTable)` has no `ignore_for_output=True` (`toc.py:5-7`); `TableProcessor.block_types` includes TOC alongside Table/Form (`table.py:35`); `BaseTable.assemble_html` emits `<table>…` (`basetable.py:38-61`). OCR skip list includes TOC so tables own it (`builders/line.py:121-135`). Impact: a WG21 PDF with a Contents page becomes body tables/lists of heading+page-number rows in Marker's markdown.

- [HIGH] **`DocumentTOCProcessor` builds metadata outline; it does not remove the visual TOC.** Evidence: walks `SectionHeader` blocks into `document.table_of_contents` (`document_toc.py:6-22`); renderer metadata exposes that list (`renderers/__init__.py:120-123`); test asserts three outline entries from headings (`tests/processors/test_document_toc_processor.py:11-13`). Impact: "TOC" in Marker means (a) extracted outline metadata and (b) a keep-and-render layout block — opposite of tomd's strip contract.

- [CRITICAL for whisker/tomd fit] **Marker default output would trip whisker `no_toc_leak` on typical WG21 papers.** Evidence: tomd strips TOC at markdown (`api.py:144-156`, `_strip_toc` at `api.py:448`) and PDF structure (`lib/toc.py` + `drop_leaked_toc_entries`); whisker hard-fails on a `Contents`/`Table of Contents` line or a page-numbered duplicate heading pair (`gates.py:143-185`). Marker has no equivalent strip processor in `default_processors` (`pdf.py:82-111`) and no `keep_toc`/`strip_toc` flag analogous to headers/footers (`README.md:131` only documents header/footer keep flags). Impact: swapping convert to Marker without a post-strip would convert a tomd/whisker hard-pass into a structural hard-fail on TOC-bearing papers (the exact class of PRs #290/#293).

- [MED] **Header/footer OCR is skipped to save VLM cost, reinforcing the strip path.** Evidence: `block_ocr_skip_types` includes `PageHeader`/`PageFooter`/`TableOfContents` with comment that OCRing dropped furniture wastes calls (`builders/line.py:121-135`). Impact: furniture is intentionally out of the recognition path; TOC is skipped for OCR because the table processor handles it, not because it is discarded.

- [LOW] **`LineNumbersProcessor` is code-margin line numbers, not page numbers.** Evidence: docstring "ignoring line numbers"; thresholds on numeric fraction of lines in a text block (`line_numbers.py:8-30`). Impact: do not cite it as page-furniture strip; page numbers ride `PageFooter` / `IgnoreTextProcessor`.

## How Marker would handle the tomd/whisker TOC contract

| Concern | tomd / whisker | Marker v2.0.0 |
|---|---|---|
| Running headers/footers | PDF edge recurrence strip (`lib/pdf/cleanup.py`) | Layout `PageHeader`/`PageFooter` + `IgnoreText` + `Marginalia`; default omit |
| Page numbers | Stripped with edge furniture | Usually `PageFooter` (description: "like a page number", `pagefooter.py:7-8`) or digit-stripped common edge text |
| In-document TOC | Stripped; body headings replace it | Layout `TableOfContents` **kept** and table-rendered; outline also copied to metadata |
| Leak gate | `no_toc_leak` hard fail (`gates.py:143-185`) | No gate; TOC in body is intended content |

**Adoption note:** furniture strip is adopt-friendly (same intent as tomd). TOC requires either a Marker post-processor that sets `TableOfContents.ignore_for_output = True` (and strips misclassified TOC-as-Text/List runs), or a tomd-style `_strip_toc` on Marker markdown before whisker scoring — otherwise Marker cannot satisfy the existing hard gate.

## False-pass hypothesis

A short WG21 paper (<3 pages) with a unique running header never repeating enough for `IgnoreTextProcessor` (`common_element_min_blocks=3`, `ignoretext.py:28-32`) and missed by the layout model as `PageHeader`, sitting slightly below the 8% header zone or taller than `max_height_frac=0.035` (`marginalia.py:27-37`): header text leaks into markdown while furniture strip "succeeds" on other pages. Whisker soft-flags misaligned regions for furniture; hard `no_toc_leak` would still be green if no TOC pattern matches.

## False-fail hypothesis

None for Marker's own convert success criteria (TOC keep is intentional). Versus **our** gates: Marker correctly converts a Contents table and whisker `no_toc_leak` hard-fails on the `Contents` label or `## 1. Introduction 3` / `## 1. Introduction` pair (`gates.py:161-176`) — a false-fail only if one wrongly treats whisker's tomd contract as Marker's bug.

## What would change my mind

A Marker config/processor that defaults `TableOfContents` (and TOC-shaped text runs) to `ignore_for_output=True` the same way `PageHeader`/`PageFooter` do, with a test asserting Contents pages do not appear in markdown — then the TOC half of this persona's CRITICAL finding collapses and the verdict upgrades toward full furniture/TOC alignment with tomd.
