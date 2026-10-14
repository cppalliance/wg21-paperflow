# 09 - Markdown-Markup Equivalence Specialist

**Verdict:** usable-with-conditions — candidate-side locate must use a markup-aware anchor ladder (raw → markup-fold → fuzzy), not `normalized_text` alone; the three local HTML→MD converters and whisker's alnum normalizer agree on *content* but diverge on every semantic delimiter the replay false-absences ignored.
**Confidence:** high

## Findings

- [CRITICAL] **`normalized_text` erases the very markup differences that cause false "missing" quotes.** `clean_string` keeps only `\w` + CJK after stripping whitespace (`metrics.py:115-126`); `ground_spans` fuzzy tiers run on `normalized_text(markdown)` (`grounding.py:206-231`). Nine-PR replay: **12/20** PDF-judge "absent" quotes were already present in markdown (`llm-evidence-reliability/00-baseline.md:16-18`) — the dominant failure is *not* missing prose but *unverified* candidate locate. Impact: any candidate check that stops at alnum-fold will pass reformatted emphasis/links/lists while still letting the sidecar claim absence; it also cannot distinguish operator-level defects (`!=` vs `==`) that `_raw_surface` and facts `surface: raw` were built to catch (`facts.py:258-266`).

- [HIGH] **olmOCR's `normalize_text` is the right *equivalence* fold for markup, not whisker's alnum strip.** Local clone: `<br>` → space, unwrap `**`/`__`/`*`/`_`, strip `<b>`/`<i>`, collapse whitespace, NFC, smart-quote/hyphen map (`packages/whisker/research/repos/olmocr/olmocr/bench/tests.py:47-80`; corroborates `redteam/olmocr.md:25-27`). Whisker ports olmOCR's *fuzzy budget* for page quotes (`grounding.py:244-278`) but not its markup strip for candidate markdown. Impact: adopt an olmOCR-style **markup-fold surface** as Tier-2 between `_raw_surface` and `normalized_text` for candidate `ground_spans`; reserve alnum-fold for content-recall/NID axes only (`metrics.py:338-340`, `CLAUDE.md` Lane 2 vs Lane 3 split).

- [HIGH] **Emphasis: three converters emit incompatible delimiters for the same HTML.** Turndown: `<em>`/`<i>` → configurable `emDelimiter` (default `_`), `<strong>`/`<b>` → `strongDelimiter` (default `**`) (`turndown/src/commonmark-rules.js:207-223`). markdownify: shared `strong_em_symbol` (`*` or `_`) for both `<em>` and `<strong>`, with optional `escape_asterisks`/`escape_underscores` and `escape_misc` on `[]\\&<`>`~=+|`, leading `#`, and digit-list patterns (`markdownify/__init__.py:27-43,419-432,517-518,718`). node-html-markdown: defaults `emDelimiter: '_'`, `strongDelimiter: '**'`, plus `lineStartEscape`/`globalEscape` overrides (`node-html-markdown/README.md:146-189`). olmOCR folds all of these away before compare. Impact: a PDF quote `"important term"` matches `**important term**`, `_important term_`, or bare `important term` after markup-fold; **must not** require the judge's delimiter choice on the candidate side.

- [HIGH] **Links: URL survives, wrapper syntax does not — locate on visible text + optional href fold.** Turndown: inline `[text](href)` or reference-link append block (`commonmark-rules.js:143-204`); escapes `<>` in destinations. markdownify: `[text](href)`, autolink `<href>` when text equals href (`__init__.py:438-456`). NHM: default `useInlineLinks: true` wraps bare URLs as `<https://…>` instead of `[url](url)` (`README.md:218-228`); optional `useLinkReferenceDefinitions` moves URLs to footer. Candidate verify should anchor on **link text / visible label** (raw or markup-fold), treat href as auxiliary (normalize `<>` vs `[]()`), and route href-only mismatches to `ambiguous`, not `absent` (`05-web.md / Q5 / CRAG`).

- [MED] **HTML residue vs pipe tables: candidate locate must be dual-surface.** markdownify emits pipe tables with colspan repetition and inferred header rows (`__init__.py:726-790`); turndown core rules have **no** table rule (tables stay as HTML unless a GFM plugin is added). tomd/whisker facts already parse **both** pipe and `<table>` grids (`tables.py`, `facts.py` table path). Impact: a quote anchored to a cell value should search parsed grid text (whitespace-normalized, lowercased for cells via `_norm_cell`, `facts.py:269-270`), not require pipe syntax in the raw markdown string; HTML-table papers (N5040 corpus) fail naive substring locate without grid projection.

- [MED] **Fences and inline code: delimiter math differs; content anchor is inside the fence.** Turndown: dynamic fence length when code contains backticks (`commonmark-rules.js:99-132`); inline code expands backtick runs (`225-243`). markdownify: `` ` `` run = max consecutive backticks + 1 (`__init__.py:493-503`); `<pre>` → `` ```lang\n…\n``` `` (`688-705`). NHM: configurable `codeFence`, `codeBlockStyle: fenced|indented` (`README.md:128-143`). Whisker `_strip_fenced_blocks` (corpus_tools) and facts `code` type use **raw** surface. Impact: candidate locate for code quotes should strip fence wrappers and language tags, then match inner payload on raw surface; fence-style differences are cosmetic (chopdiff pattern, `05-web.md / Q3 / chopdiff`).

- [MED] **List markers and entities: fold markers, not words.** markdownify: `-`/`+/`*` bullets with depth rotation; OL `N.` from `start` + sibling index (`__init__.py:628-663`). Turndown: `bulletListMarker` + three-space indent continuation (`commonmark-rules.js:47-77`). olmOCR does not strip list markers explicitly but whitespace collapse merges `1.` prefix with text. HTML entities (`&amp;`, `&lt;`) decode at parse time in all three converters (DOM / BeautifulSoup); whisker has no entity pass in verify — NFC + quote map live in olmOCR only. Impact: entity/typography diffs belong in markup-fold (NFC + smart-quote table); list-marker diffs belong in **line-start anchor regex** (`^\s*([-*+]|\d+[.)])\s+`) before content match, not in alnum-fold.

- [LOW] **Golden lane `normalize_for_exact_lane` is intentionally not equivalence — it preserves all markup.** Only CRLF → LF, trailing space trim, EOF newline (`golden.py:79-90`). Impact: do not conflate Lane 1 byte stability with candidate-absence equivalence; quote verify needs the olmOCR/anchor surfaces, not golden normalization.

## Construct comparison (local clones vs whisker verify)

| Construct | turndown | markdownify | node-html-markdown | whisker today | Anchor-first locate rule |
| --- | --- | --- | --- | --- | --- |
| **Emphasis** | `*…*` / `_…_`, `**…**` | `*…*` or `_…*` (one symbol) | `_` em, `**` strong | stripped by `normalized_text` | markup-fold (olmOCR) then token `\w+` chain |
| **Links** | `[t](u)` or ref defs | `[t](u)`, `<u>` autolink | `<u>` or ref defs | label+url punctuation stripped | anchor on visible `t`; href fold optional |
| **Entities** | DOM decode | BS decode | parser decode | none in verify | NFC + olmOCR quote map at markup-fold |
| **HTML blocks** | no table in core | pipe + colspan | block list incl. TABLE | facts parse HTML+pipe | project cell text via `parse_*_tables` |
| **Fences** | dynamic ``` count | ``` + lang | configurable fence | raw `code` facts | strip fence/lang; match inner raw |
| **List markers** | `-`/`*`/ `1.`  | rot bullets, `N.` | `bulletMarker` | lost in alnum-fold | strip `^[-*+\d.]+\s` per line, then raw |
| **Tables** | (none core) | pipe + infer header | (turndown-like) | TEDS/GriTS + cell facts | cell `_norm_cell` anchor, not pipe chars |

## How to locate same content without erasing semantic symbols

Use **anchors only** — substring / ordered / regex tripwires on named surfaces (`anchors.py:8-24,66-73`), extended to quote-verify:

1. **Tier A — `surface: raw` anchor** (`anchors.py:47-48`, `facts.py:258-266`): `str.find` / monotonic token DP (`grounding.py:171-228`) on whitespace-collapsed text. Preserves `C++`, `!=`, `[P1234R5]`, `$`, `^`, `_`. Use for code, xrefs, math relations, and short LLM quotes copied from PDF text layer.

2. **Tier B — markup-fold anchor** (olmOCR `normalize_text`, not yet wired to candidate `ground_spans`): unwrap emphasis, strip `<b>/<i>`, collapse WS, NFC, typography map. Locates the same *words* when tomd used `**foo**` and the judge quoted `foo`. Does **not** drop `=`, `^`, `_` (contrast `normalized_text`).

3. **Tier C — structural anchors**: table cell via grid parser; code via fence strip; list item via line-start marker strip then Tier A/B on remainder; link via visible label.

4. **Tier D — `normalized_text` / fuzzy ratio**: last resort for OCR-noisy PDF quotes only (`grounding.py:230-237`); emit `candidate: ambiguous`, never `absent`, when only Tier D hits (`05-web.md:152-159,182-190`).

5. **Ordered anchors** for multi-span quotes: `ordered` chain in `anchors.py:71-72` — same pattern as olmOCR `ORDER` tests and replay PR #290 duplicate date lines (present twice: order-agnostic `present`, order-sensitive `ordered`).

**Do not** use alnum-only fold to prove absence of content that might survive as markup, HTML table, or reflowed list — that path caused the **40%** evidence precision (`00-baseline.md:21-24`).

## False-pass hypothesis

PR #285: five date lines quoted "missing" but present verbatim (some duplicated). Source-only `ground_spans(pdf_text)` passes; if candidate check used **`normalized_text` only**, duplicate copies and punctuation variants still match — but a stricter **raw anchor** on the exact PDF line including punctuation would correctly return `present` and drop the false-absent quote. Failure mode if we skip Tier A: none (already present). Failure mode if we use **only** Tier D: false `present` when the line was reformatted to a heading or link label only — unlikely here; the replay case is false absent, not false present.

## False-fail hypothesis

PR #293: five `constexpr` declarations genuinely absent. Aggressive **markup-fold** could false-fail if declarations survived only inside an HTML `<code>` block or indented pre without fence while the judge quoted plain text — Tier A raw + fence strip should still find them; if the converter dropped them entirely, correct `absent`. **Over-tight raw anchor** (requiring exact PDF whitespace when tomd reflowed to `constexpr int x = 0;` on one line) false-fails → route to Tier B/C fuzzy with olmOCR length-relative budget (`tests.py:168-169`, `ground_page_quotes` pattern).

## What would change my mind

A labeled holdout (≥30 quotes, human `{present-as-markup, present-as-prose, absent}`) where **markup-fold + raw anchors** false-absent rate exceeds **raw-only**, or where olmOCR-style fold false-passes on operator/math swaps that `_math_surface`/`surface: raw` facts catch. Until then, the local converter survey and 12/20 replay FPs support markup-aware anchors over single-surface normalization.

### Recommended candidate-side wiring (anchors-only, no new deps)

| Step | Surface | Reuse |
| --- | --- | --- |
| 1 | raw substring / exact token interval | `ground_spans` exact tier, `_raw_surface` |
| 2 | markup-fold substring | port olmOCR `normalize_text` (40 lines, stdlib+re) |
| 3 | table cell / code inner / link label | `tables.py`, facts `_strip_fenced_blocks`, manual label extract |
| 4 | fuzzy + `ambiguous` | existing `partial_ratio` + olmOCR length guard |
| 5 | demote LLM absent | LitRAG pattern (`05-web.md / Q2`): candidate hit → `present`, override judge |

Report provenance: local clones under `packages/whisker/research/repos/` (gitignored; read via explicit path / `rg --no-ignore-vcs` per `00-baseline.md:74-86`).
