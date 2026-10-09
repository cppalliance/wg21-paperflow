# 08 - Dehyphenation and Line-Wrap Specialist

**Verdict:** usable-with-conditions — tomd and olmOCR already define the right prose-equivalence contract; whisker's PDF lane applies dehyphenation only on the per-page recall screen, not on monolith grounding or candidate-side checks, so line-wrap and cross-page join artifacts are the dominant false-absent class in the 40% evidence-precision miss.
**Confidence:** high

## Findings

- [CRITICAL] **Whisker dehyphenates only for the per-page recall screen; monolith grounding and the LLM see raw wrapped PDF text.** `pdf_judge.py:96-108` defines `_DEHYPHENATE_RE = r"(\w)-\n(\w)"` and applies it in `screen_pages` (`:299`) and page escalation (`:561`) but **not** to `pdf_text = normalize_textlayer(pages)` passed to the monolith judge or `ground_spans(spans, pdf_text)` (`:464`, `:519`). The regex is intra-page only (`\n`, not `\n\n` page breaks). Impact: a quote `"implementa-\ntion"` grounded in raw PDF text fails naive candidate substring match against markdown `"implementation"`; this is edge-case 4 in `research/per-page-judging/SYNTHESIS.md:123-125` and a direct contributor to PR #285/#290 false-absent quotes (`00-baseline.md:17-18`).

- [CRITICAL] **Cross-page paragraph joins leave dangling page tails that look absent though the full sentence exists once in markdown.** tomd `_join_cross_page` merges when the last block on page N lacks terminal punctuation and page N+1 starts lowercase (`tomd/lib/pdf/cleanup.py:322-363`; contract `tomd/CLAUDE.md:230-232`). Page-scoped raw text for page N ends mid-sentence; converted markdown holds the joined unwrapped line. `20-false-fail-hunter.md:16` documents p3556r0 (`"listed in"` / `"Table 1 to try..."`). Impact: page escalation asking "is this page's content missing?" will quote dangling tails; without join-aware candidate matching, every cross-page join site is a false-absent candidate.

- [HIGH] **tomd's dehyphenation contract is stricter and better specified than whisker's partial port.** tomd joins `word-` + `lowercase` across lines, skipping compound prefixes `self`, `non`, `well`, `cross` (`cleanup.py:508-525`, `COMPOUND_PREFIXES`; mirrored in `check_content.py:206-218`). Whisker `_dehyphenate` has no compound-prefix guard and only handles `\w-\n\w`. `check_content.py` applies `_dehyphenate` symmetrically to **both** source and markdown before token comparison (`:221-227`). Impact: candidate-absence verification should reuse tomd's compound-aware rule, not whisker's screen-only regex; otherwise `self-\ncontained` false-clears or false-fails depending on which side was normalized.

- [HIGH] **Prose unwrap is sanctioned but asymmetric across the three local stacks.** tomd emits each paragraph as one unwrapped line (`tomd/CLAUDE.md:138`, `emit.py`); PDF judge prompt states this explicitly (`pdf_judge.py:162-163`). **pymupdf4llm** joins spans per line with `" ".join([s["text"] for s in spans])` and inserts `\n` only on block change or vertical-gap heuristics (`pymupdf4llm/src/helpers/pymupdf_rag.py:639`, `:700-711`); no dehyphenation pass in the clone. **opendataloader-pdf** defaults to merging line breaks into paragraphs (`Config.java:225-239`, `keepLineBreaks`); table cells always fold `LINE_BREAK → SPACE` (`MarkdownGenerator.java:333-334`); optional `--keep-line-breaks` preserves intra-block breaks. Impact: the PDF text layer the judge sees is multi-line wrapped; the candidate is single-line prose; verbatim quote grounding is structurally biased toward false absence.

- [HIGH] **Code and monospace blocks must be excluded from prose equivalence; wrapped code is a distinct false-absent class.** tomd contract: fenced code lines are never reflowed (`tapetum_llm.md:48`); pymupdf4llm switches code mode on all-mono lines and preserves per-line indentation (`pymupdf_rag.py:681-692`). PDF `page.get_text("text")` often hard-wraps long `requires` clauses and grammar productions across lines; markdown keeps one logical line per source line inside fences. Impact: quoting a wrapped PDF code fragment against unwrapped or differently wrapped markdown produces false absence even when semantics match; prose dehyphenation rules applied to code are a false-pass vector (merged identifiers).

- [MED] **Ligatures and dash normalization are handled inconsistently across surfaces.** `check_content.py` applies NFKC and smart-quote translation before dehyphenation (`:223-225`). `metrics.normalized_text` runs `textblock2unicode` + `clean_string`, which strips all newlines and non-alnum but does **not** NFKC (`metrics.py:118-126`, `:338-340`). pymupdf4llm normalizes Unicode dash codepoints to ASCII `-` in image path refs only (`utils.py:186-193`), not in body text. opendataloader has no ligature-specific pass in the scanned Java core. Impact: PDF text layer `ﬁ` (U+FB01) vs markdown `fi` may fail exact grounding while passing `normalized_text`; candidate absence checks must pick one deterministic fold (NFKC minimum) and apply it to **both** quote and candidate.

- [MED] **`ground_page_quotes` already normalizes whitespace but not dehyphenation or cross-page join.** `grounding.py:261-274` runs `normalized_text` on page text and quote, then olmOCR length-relative `partial_ratio` (`threshold = 1.0 - PAGE_QUOTE_MAX_DIFFS / len(quote)`, `PAGE_QUOTE_MAX_DIFFS=2`). `normalized_text` collapses newlines inside `clean_string`, which helps unwrap equivalence but erases hyphen-boundary evidence and cannot reconstruct cross-page joins. Impact: page-quote grounding tolerates minor char drift but not systematic wrap/dehyphen/join reformats; candidate-side matching needs a richer, contract-aware surface than `normalized_text` alone.

- [LOW] **Neither pymupdf4llm nor opendataloader-pdf ships quote-level absence verification; their line policies inform equivalence only.** pymupdf4llm QA is byte-exact golden compare (`research/llm-readability/repo-scan/pymupdf4llm.md:15-24`). opendataloader uses structural NID/TEDS means (`repo-scan/opendataloader-pdf.md:39-44`). Portable pattern from olmOCR (`05-web.md:12-18`, `redteam/olmocr.md:27-28`): normalize both sides identically, then symmetric presence/absence with length-relative tolerance.

## False-pass hypothesis

A judge quotes `"non-\ncompliant"` from raw PDF text. Candidate markdown correctly preserves the compound `"non-compliant"`. If candidate-side matching applies whisker's naive `_dehyphenate` (no compound-prefix guard) before locate, the quote normalizes to `"noncompliant"` while the candidate stays `"non-compliant"`; a loose `partial_ratio` over the full document (`grounding.py:232-236`) could mark the quote `refuted_present` and drop a genuine semantic defect elsewhere. Compound-aware dehyphenation (`tomd/cleanup.py:517`) prevents this on the converter side but must be mirrored in the verifier.

## False-fail hypothesis

PR #285 class: judge quotes a 15-word PDF fragment split across three raw lines with trailing hyphens on lines 1-2; markdown holds the same words as one unwrapped line (`00-baseline.md:17`). Source `ground_spans` succeeds against raw `pdf_text`; without prose equivalence on the candidate, `_present_within` fails; sidecar labels `"present in PDF text layer, absent from markdown"` (`00-baseline.md:37-38`). Same mechanism for cross-page dangling tails (`20-false-fail-hunter.md:16`) and date lines duplicated in YAML front matter plus body (`00-baseline.md:18`).

## Minimal deterministic equivalence rules

Research artifact only. Scope: candidate-side locate for LLM missing-content quotes after source grounding succeeds (`00-baseline.md:61-68`, `02-candidate-absence.md:16-24`). Stdlib + existing whisker/toml helpers; no new dependency.

### Rule 0 — Route by surface before any normalization

| Surface | Detection | Equivalence allowed |
|---------|-----------|-------------------|
| `prose` | default when quote is not inside a fence/table/math heuristic | unwrap, dehyphenate, whitespace collapse |
| `code` | quote lines match `CODE_LINE_RE` (leading whitespace, `{};`, `::`, `requires`) or lie inside markdown fence span | **none** beyond NFC + NBSP→space; preserve `\n` count |
| `table_cell` | quote from table context or pipe-heavy | collapse internal whitespace/newlines to single space only |
| `math` | quote contains `^`, `_`, `=`, `\`, `$` | use `facts._math_surface` fold only; never `clean_string` |

### Rule 1 — Prose equivalence normalize `E_prose(text)` (shared by quote and candidate window)

Apply in order, deterministically:

1. `unicodedata.normalize("NFKC", text)`
2. Replace NBSP and Unicode spaces with ASCII space (tomd `_collapse_spaces` pattern)
3. Smart-quote fold (`check_content._SMART_QUOTE_TABLE`)
4. **Dehyphenate line breaks:** `re.sub(r"(\w)-\s+(\w)", repl, text)` where `repl` keeps hyphen when left token lowercased is in `{"self","non","well","cross"}` else concatenates (tomd `cleanup.py:516-518`, `check_content.py:212-216`)
5. **Unwrap:** `re.sub(r"\s+", " ", text).strip()` (prose only; collapses hard wraps)
6. Strip markdown inline markup for comparison only: `**`, `_`, `` ` ``, `<ins>`, `<del>`, `~~` (olmOCR strip pattern, `05-web.md:12-18`)
7. Lowercase for locate only (does not gate code/math surfaces)

Do **not** apply steps 4-5 to `code` surface. Do **not** apply step 6 to `code`/`math`.

### Rule 2 — Cross-page join extension (page-scoped quotes only)

When quote `q` comes from page-escalation (`pdf_judge.py:561`) and `E_prose(q)` fails against full candidate:

1. Let `tail =` last 40 chars of `E_prose(page_text)` (deterministic cap)
2. Let `head =` first 40 chars of `E_prose(page_text[+1])` when page exists
3. Also test candidate locate against `E_prose(tail + " " + head)` and `E_prose(tail + head)` (dehyphenation inside step 4 handles `tail[-1]=='-'` cases)
4. If any variant matches within budget → `refuted_present`, `reason_code=cross_page_join`

Model boundary: revise if labeled replay shows join-extension false-clears true page-local absence.

### Rule 3 — Candidate locate after equivalence

On the routed surface:

1. `needle = E_surface(quote)` (Rule 1 for prose; identity for code)
2. `haystack =` full candidate for prose; fence-bounded region for code; table cell neighborhood for table
3. Run `facts._present_within(needle, haystack, max_diffs)` (`facts.py:324-326`)
4. `max_diffs`: `PAGE_QUOTE_MAX_DIFFS` (2) if `len(needle) < 40`, else `max(2, round(len(needle) * (1 - EVIDENCE_FUZZY_FLOOR)))` capped at `len(needle)//4` (`02-candidate-absence.md:20`, `grounding.py:272-273`)

### Rule 4 — Tri-state outcomes (per quote)

| Outcome | Condition | Sidecar |
|---------|-----------|---------|
| `refuted_present` | step 3 succeeds on prose, code, or join-extension | drop quote; `reason_code` ∈ `{dehyphenation, line_unwrap, cross_page_join, markup_equivalence}` |
| `confirmed_absent` | source grounded, all candidate locates fail | retain quote |
| `ambiguous` | only whole-doc `partial_ratio` ≥ floor without `_present_within` confirmation (`EVIDENCE_MIN_FUZZY_CHARS`, `grounding.py:232-237`) | demote; do not count as absent |

### Rule 5 — Screen alignment (cheap consistency fix)

Apply the same `E_prose` to `pdf_text` (or per-page text) before monolith `content_recall` and when building the LLM's RAW PDF TEXT block, so the recall screen and the judge see the same surface the candidate contract describes (`pdf_judge.py:162-163`). Keep a parallel `raw_pdf_text` artifact for verbatim source-grounding audit if needed.

### What not to add

- No LLM adjudication of equivalence (AbsenceBench weakness, `05-web.md:37-43`)
- No global `normalized_text` equality for code/math quotes (`metrics.py:364-365` collapses paragraphs to single tokens; wrong granularity for locate)
- No pymupdf4llm-style vertical-gap paragraph guessing in the verifier (geometry is unavailable in markdown)
- No `--keep-line-breaks` toggle in whisker; tomd's unwrapped prose contract is fixed

## What would change my mind

A nine-PR replay (`00-baseline.md:11-12`) applying Rules 0-4 with per-quote labels showing evidence precision ≥ 0.90 on the 20-quote set while retaining all eight confirmed-absent quotes (PR #284 3/5 + PR #293 5/5), OR one counterexample where cross-page join-extension (Rule 2) marks a genuinely absent page-local fragment as `refuted_present`.
