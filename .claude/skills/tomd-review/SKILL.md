---
name: tomd-review
description: Use when reviewing a tomd-converted WG21 paper's candidate ideal golden against its source for the tomd golden QA workflow. Compares the source (HTML directly, PDF as rendered page images) to the candidate markdown and emits a punch-list of structural divergences only, never verbatim-content edits.
---

# tomd Review Ideal

## Overview

The structural-review step of the tomd golden QA workflow. Given a WG21 paper's
**source** and a **candidate ideal** markdown (seeded from tomd's own conversion
with `tomd generate`, then hand-corrected), find where the candidate's STRUCTURE
diverges from the source and report it as a punch-list.

This is the optional **de-anchoring** check: because the candidate is seeded from
tomd's own output, a human correcting it can rubber-stamp tomd's structural
mistakes. An independent reviewer reading the source catches what the anchored
human misses.

Two hard rules make the review trustworthy:

1. **Structure only.** Flag heading levels, list nesting, code fencing, tables,
   front-matter order, and chrome/TOC leakage. Do NOT flag wording, paraphrase,
   or verbatim content: a human owns content fidelity, and the comparator scores
   content separately. A reworded note is out of scope; a `###` that should be
   `##` is in scope.
2. **Source is ground truth.** Judge the candidate against what the source shows,
   never against tomd's behavior or what would be convenient to convert.

This skill backs both the `tomd review <paper_id>` command (which reads this file
and embeds it in a headless prompt) and interactive use in a Claude Code session.
It is the single source of truth for the review contract.

## Input by source type

Structure is a layout signal (columns, font sizes, indentation, fences), so the
review needs an input that preserves those signals.

- **HTML** (`packages/tomd/tests/fixtures/golden/sources/<stem>.html`): read the
  source HTML directly. The DOM makes headings, lists, tables, and
  `<ins>`/`<del>` wording explicit.
- **PDF** (`packages/tomd/tests/fixtures/golden/sources/<stem>.pdf`): read the
  **rendered page images**. `tomd add` / `tomd render` writes them under
  `tests/fixtures/golden/.render/<stem>/` as `page-001.png`, `page-002.png`, ...;
  read those with the Read tool. Plain extracted PDF text is **FORBIDDEN**: it
  flattens away the columns, font sizes, and indentation that define structure.

## The contract: what correct structure looks like

The candidate targets tomd's output contract (`packages/tomd/src/tomd/CLAUDE.md`,
the full reference). The load-bearing structural rules to review against:

- **Headings** derive from section-number depth, with an H2 body floor. H1 (`#`)
  is reserved for the front-matter title, so body headings start at H2. A
  top-level numbered section (`1`, `2`, ...) is `##`; depth maps as `depth + 1`
  (`2.1` is `###`, `2.1.3` is `####`). Known unnumbered sections (`Abstract`,
  `Revision History`, `References`, `Acknowledgements`, `Motivation`, `Wording`)
  are top-level `##`. The leading section number is stripped from heading text
  (`## Introduction`, not `## 2 Introduction`).
- **Lists** are nested bullets using the source marker (`-` for bullets, `1.` for
  ordered), two spaces of indent per nesting level.
- **Code** is fenced with a language label (` ```cpp `). One source listing is
  one fenced block: never split a listing across fences, never merge two listings
  into one, never drop the language label.
- **Tables** are reconstructed as GitHub-flavored markdown tables (header row,
  `---` separator, one row per source row).
- **Front matter** is YAML in the FIXED key order: `title`, `document`, `date`,
  `intent`, `audience`, `reply-to`. Missing keys are omitted (no placeholders).
- **Chrome and the table of contents are stripped**: page numbers, running
  headers/footers, the `Contents` block, self-link glyphs, view-control widgets.

## Output: the punch-list

Emit a punch-list of STRUCTURAL divergences from that contract only. For each
divergence give:

- the **location** (heading text, section number, or a nearby line),
- what the **candidate** does,
- what the **source** shows.

Example: `§4 "Wording" is H3 (###); the source shows it as a top-level section,
so it should be H2 (##).`

If there are no structural divergences, say exactly `No structural divergences
found.` Do not flag wording, paraphrase, or verbatim content. Output only the
punch-list: no preamble, no commentary.

## After the review

The punch-list is advisory. The maintainer applies the structural fixes to the
candidate ideal by hand (the `tomd-surgical-edits` skill helps), then runs
`tomd bless <paper_id>` (which rejects an uncorrected seed and records the
baseline). The human, reading the source, remains the authority on verbatim
content.
