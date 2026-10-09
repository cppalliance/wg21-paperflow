# 07 - Normalization-Loss Auditor

**Verdict:** usable-with-conditions — whisker already carries the right *family* of normalizers (`raw`, token, math, content-collapsed), but tapetum grounding and the planned candidate-absence path over-index on `normalized_text`, which erases the very surface forms absence claims must distinguish; a layered verifier is required, not a stronger single fold.
**Confidence:** high

## Findings

- [CRITICAL] `normalized_text` is the wrong sole oracle for candidate-absence verification. Evidence: `metrics.py:338-340` (`clean_string(textblock2unicode(text))`), `metrics.py:115-126` (`_CLEAN_KEEP_RE` keeps `\w` + CJK only); `00-baseline.md:52-53` explicitly marks it punctuation-insensitive and unsuitable alone. Runtime (2026-07-16): `normalized_text("x != y") == normalized_text("x == y")` → both `'xy'`; `normalized_text("Hello, world!") == normalized_text("Hello world")` → both `'Helloworld'`; `normalized_text("x^2") == normalized_text("x2")` → both `'x2'`. Impact: a quote correctly present in the candidate under different punctuation, operators, or exponent formatting is indistinguishable from genuinely absent content, reproducing the 40% candidate-absence precision failure (`00-baseline.md:21-24`).
- [CRITICAL] Tapetum grounding folds both haystack and quote through `normalized_text`, so corrupted quotes ground against faithful markdown. Evidence: `grounding.py:206-237` (`norm_md = normalized_text(markdown)`, `norm_quote = normalized_text(span.quote)`); `pdf_judge.py:513-520` / `grounding.py:244-278` apply the same fold to page quotes. Runtime: markdown `"The energy is $E = mc^2$ as shown."` with quote `"$E = mc$"` → `norm_quote='mc'`, substring hit in `norm_md='Theenergyismc2asshown'`, `ground_spans` keeps the span (reproduced 2026-07-16; aligns with `research/llm-stack/22-grounding-robustness-auditor.md:8`). Impact: exponent loss, sqrt collapse, and dropped math wrappers pass source-side grounding and would also pass a symmetric candidate-side check at this layer — the inverse of absence verification.
- [HIGH] `content_tokens` and `normalized_text` disagree on what constitutes a "word", creating a split brain across whisker lanes. Evidence: `metrics.py:355-369` (`_CONTENT_TOKEN_RE = r"\w+"` on `textblock2unicode(...).lower()`); `test_metrics.py:160-163` (`"Hello, World! Foo-bar"` → `["hello","world","foo","bar"]`). Runtime: `content_tokens("foo-bar")` → `['foo','bar']` but `content_tokens("foobar")` → `['foobar']`; `normalized_text("foo-bar") == normalized_text("foobar")` → both `'foobar'`. `content_recall` and per-page screen use tokens (`score.py` path via `content_tokens`); grounding fuzzy tiers use `normalized_text`. Impact: a hyphenation/dehyphenation delta can look "present" to NID/recall while a quote-level absence check at `normalized_text` also says present — no layer flags the semantic split.
- [HIGH] Underscores survive `clean_string` but hyphens do not, producing asymmetric identifier behavior. Evidence: `metrics.py:115` (`\w` in Python includes `_`); runtime: `normalized_text("foo_bar")` → `'foo_bar'`, `normalized_text("foobar")` → `'foobar'` (not equal); `normalized_text("foo-bar")` → `'foobar'` (equal to plain `foobar`). Impact: `snake_case` identifier loss is detectable at the content-collapsed layer; `kebab-case` or dehyphenated reflow loss is not — WG21 papers mix both (`P1234R0`, `std::vector`, macro names).
- [HIGH] Local conversion repos use *shallower* normalizers for presence/absence tests than whisker uses for grounding. Evidence: olmOCR `normalize_text` (`packages/whisker/research/repos/olmocr/olmocr/bench/tests.py:47-80`) strips Markdown/HTML emphasis, collapses whitespace, applies NFC, maps smart quotes, but **keeps** operators and alnum punctuation; `TextPresenceTest` runs the same function for `PRESENT` and `ABSENT` with length-relative `partial_ratio` (`tests.py:128-182`). Marker `MarkdownCleaner` (`marker/benchmarks/overall/scorers/clean.py:12-76`) round-trips through **pandoc** MD→HTML→MD, then lowercases and collapses whitespace — still keeps `|`, `^`, `_` in prose. Dolphin `markdown_utils.py` chains LaTeX canon, repeat truncation, and table-HTML strip *before* scoring, never alnum-collapsing. Impact: porting olmOCR-style absence without adding whisker-specific layers would be **stricter** than current grounding (fewer false-pass absence claims) but still blind to math structure unless `MathTest`-style rendering is added (`tests.py:549-604`).
- [MED] Whisker already implements the layered surfaces absence verification needs, but they are siloed by lane. Evidence: `facts.py:238-266` (`_math_surface` keeps `^`, `_`, `=`; `_raw_surface` keeps operators and case); `anchors.py:46-48,121-124` (`surface: normalized | raw`); `golden.py:79-90` (`normalize_for_exact_lane` — EOL/trailing-space only); `metrics.py:84-86` (`_normalize_text` — whitespace collapse for `text_nid` only, distinct from `normalized_text`). Impact: the fix is orchestration (pick surface per claim type), not inventing a new normalizer; `05-web.md:192-194` confirms olmOCR-style dual locate is the lowest-risk pattern.
- [MED] Markdown-syntax stripping is intentional on the fidelity axis but toxic for markup-specific absence claims. Evidence: `test_metrics.py:195-199` (`clean_string("# Title\n\n**Hello**, world! | a | b |")` → `"TitleHelloworldab"`); olmOCR `normalize_text` removes `**`/`__`/`<b>` but leaves cell digits and pipes. Runtime: `normalized_text("| bar | 100 |")` → `'bar100'`, `normalized_text("| bar | 99 |")` → `'bar99'` (distinguishable); but `normalized_text("## Title\n\n**bold**") == normalized_text("Title bold")` → both `'Titlebold'`. Impact: table *cell-value swaps* can still be caught at the collapsed layer when digits differ; table *structure* loss that preserves the same digit stream (column reorder with same values) is not — needs `table` facts or TEDS, not text normalization.
- [LOW] Unicode normalization is partial and repo-dependent. Evidence: olmOCR applies `unicodedata.normalize("NFC", ...)` (`tests.py:71`); whisker `textblock2unicode` + `replace_textcircle` (`metrics.py:98-126`) fold circled glyphs and inline LaTeX but do not NFC-compose; `test_metrics.py:202-209` documents circled-digit folding. Impact: NFC/NFKD divergence between PDF text layer and markdown (composed vs decomposed accents, ligatures) can false-fail raw exact match and false-pass collapsed match; rare on English WG21 prose, material for author names and math symbols.

## Defect taxonomy (normalization-loss classes)

Each class lists what whisker **loses** at `normalized_text`, what **survives** at a shallower layer, and the **false-pass / false-fail** risk for absence verification.

| Class | Stripped or collapsed by `normalized_text` | Survives at | Absence false-pass (claims absent, present) | Absence false-fail (claims absent, truly absent) |
|-------|---------------------------------------------|-------------|---------------------------------------------|--------------------------------------------------|
| **Punctuation** | `, . ; : ' "` and most ASCII punctuation | `raw`, olmOCR `normalize_text` | HIGH — comma/quote reflow reads absent | LOW — different skeletons rare |
| **Symbols** | `@ # % & + ~ \` and non-alnum except `_` | `raw` | HIGH — symbol-only anchors (copyright, trademarks) | LOW |
| **Code operators** | `!= == <= >= -> :: && \|\|` (all non-`\w`) | `raw`, `code` facts | CRITICAL — `x != y` vs `x == y` both → `xy` | LOW |
| **Underscores** | *Not stripped* (`\w`) | `normalized_text`, `content_tokens` as `foo_bar` token | MED — loss of `_` in `foo_bar`→`foobar` is detectable | LOW |
| **Unicode** | LaTeX folded via `textblock2unicode`; accents may survive inconsistently | NFC (olmOCR), `math_surface` | MED — `café` vs `cafe` encoding paths | MED — OCR glyph vs Unicode form |
| **Whitespace** | All whitespace removed in `clean_string` | `raw` (collapse), `normalize_for_exact_lane` (EOL only) | HIGH — reflow/dehyphenation invisible | LOW |
| **Markdown** | `#`, `*`, `\|`, fences, links — syntax chars dropped | olmOCR strip (content kept), `golden` exact | HIGH — markup-only diffs | LOW — true content drops usually remove alnum |

### Worked collapse examples (reproduced 2026-07-16)

```
Input A                    Input B                 normalized_text equal?   content_tokens differ?
Hello, world!              Hello world             True                    No (same tokens)
x != y                     x == y                  True                    No
x^2                        x2                      True                    Yes (['x','2'] vs ['x2'])
foo-bar                    foobar                  True                    Yes (['foo','bar'] vs ['foobar'])
foo_bar                    foobar                  False                   Yes
| bar | 100 |              | bar | 99 |            False                   Yes
$E = mc^2$ (in md)         quote $E = mc$          substring pass          N/A (grounding)
```

## Comparison: whisker vs local repos vs pandoc

| Layer | whisker | olmOCR bench | Marker (+ pandoc) | Dolphin | Intended use |
|-------|---------|--------------|-------------------|---------|--------------|
| Exact bytes | `golden.normalize_for_exact_lane` | — | — | — | Stability snapshots |
| Raw + WS collapse | `facts._raw_surface` | partial (after MD strip) | after pandoc RT | — | Operator/code absence |
| Markdown-aware strip | — | `normalize_text` | `MarkdownCleaner` | table HTML strip | Markup-equivalent presence |
| Token /\w+ | `content_tokens`, `grounding._tokenize` | — | post-RT tokens implicit | — | Recall, ordered chains |
| LaTeX → unicode | `textblock2unicode` | `MathTest` render compare | `latex2mathml` in cleaner | `markdown_utils` canon | Math presence |
| Alnum collapse | `normalized_text` | — | lowercase only | repeat truncation | Fidelity NID, **not absence** |
| Math structure | `facts._math_surface` | `MathTest` (KaTeX render) | — | LaTeX transforms | Exponent/operator fidelity |

**Pandoc** (`packages/whisker/research/repos/pandoc`, local clone present per `00-baseline.md:75-83`) has no single "normalize" function in-tree; Marker uses it as a **round-trip canonicalizer** (`clean.py:39-76`) to absorb fence/heading variant before diff. That is a distinct layer whisker does not currently expose on the tapetum path.

## Layered normalizers required for absence verification

Absence is asymmetric: proving content **present** tolerates aggressive folding; proving content **absent** must start strict and only relax with an explicit `ambiguous` band (`05-web.md:17-18`, `00-baseline.md:67-68`). Recommended stack, bottom (strict) to top (permissive):

```text
L0  raw_exact      Verbatim substring on candidate markdown (and PDF text layer for source).
                  Use for: pdf_judge quotes, constexpr declarations, date lines.
                  Failure mode: reflow, dehyphenation, markup wrapping → false-fail.

L1  raw_fuzzy      olmOCR length-relative partial_ratio on whitespace-collapsed raw
                  (`PAGE_QUOTE_MAX_DIFFS` pattern, `grounding.py:272-273`).
                  Use for: OCR glyph drift, soft hyphen, minor whitespace.
                  Failure mode: short generic quotes → false-pass (whole-doc haystack).

L2  markdown_aware olmOCR-style strip (`tests.py:47-80`): emphasis/HTML/br, NFC, smart quotes.
                  Use for: "present under different bold/italic/link syntax".
                  Failure mode: still keeps operators; does not solve math structure.

L3  token_chain    `content_tokens` or `grounding._tokenize` monotonic DP (`grounding.py:171-228`).
                  Use for: dehyphenation (`foo-bar` vs `foobar`), word reorder within tolerance.
                  Failure mode: `x^2` vs `x2` token mismatch → false-fail; `x != y` vs `x == y` → false-pass.

L4  operator_raw   `facts._raw_surface` / `surface: raw` / `code` fact type.
                  Use for: `!=`, `::`, `constexpr`, macro names, revision-sensitive xrefs.
                  Failure mode: reflow across line breaks without raw needle.

L5  math_surface   `facts._math_surface` (keeps `^`, `_`, `=`).
                  Use for: exponent/sqrt/relational math absence claims.
                  Failure mode: rendering differences between `$...$` and unicode fold.

L6  content_collapsed  `normalized_text` / `clean_string`.
                  Use for: confirming coarse content *presence* after formatting migration only.
                  MUST NOT gate absence alone (`00-baseline.md:52-53`).
                  Route to `ambiguous`, not `absent`.
```

### Routing policy (per quote)

1. Classify the quote (prose, code, math, table cell, date/number, markup).
2. Run **candidate locate** top-down: L0 → L1 → … until hit or exhausted.
3. Run **source locate** with the same layer (bidirectional symmetry per `05-web.md:13-18`).
4. Emit `present | absent | ambiguous`:
   - `present` — candidate hit at L0–L3 (claim "missing" is false).
   - `absent` — source hit at L0–L2 AND candidate miss at L0–L2 (strict bands agree).
   - `ambiguous` — source hit at Lk but candidate only hits at L6, or layers disagree.
5. Never label `absent` on L6 match alone; demote LLM verdict when all deciding quotes are `present` or `ambiguous` (`00-baseline.md:67-68`).

### What to reuse vs add

| Need | Reuse today | Gap |
|------|-------------|-----|
| Raw exact/fuzzy | `ground_page_quotes`, `facts._present_within` | Wire to candidate markdown, not only PDF page |
| Token alignment | `ground_spans` exact tier | Candidate-side mirror; return `char_interval` |
| Markdown strip | Port olmOCR `normalize_text` as optional L2 (stdlib + `unicodedata`, no dep) | Not in whisker yet |
| Math | `facts._math_surface`, olmOCR `MathTest` pattern | Not on tapetum path |
| Collapsed | `normalized_text` | Restrict to `ambiguous` resolver only |

No new dependency is justified: olmOCR's `normalize_text` is ~35 lines of stdlib/`re`; Marker already proves pandoc round-trip is optional and environment-dependent (`clean.py:47-56`).

## False-pass hypothesis

PR #285 date-line replay (`00-baseline.md:18`): the PDF judge quotes `"2024-10-15"` as missing. Candidate markdown contains the same digits with different surrounding punctuation or YAML front-matter placement. `normalized_text(candidate)` still contains `20241015` as a substring of the folded skeleton, so a candidate-side check at L6 returns hit → the quote is mislabeled absent, sustaining the 40% evidence-precision failure even after bidirectional grounding is added unless L0 raw exact is tried first and fails before L6 is consulted.

## False-fail hypothesis

A faithful conversion hyphenates a line-break reflow (`"implementa-\ntion"` → `"implementation"` in prose, legitimate tomd behavior). L0 raw exact on the PDF-text-layer quote `"implementa-"` misses the candidate; L3 token chain on `["implementa", "tion"]` vs `["implementation"]` also misses; only L6 collapsed match succeeds. A strict policy that treats anything short of L0 as `absent` would false-fail; the `ambiguous` band (source L0 hit, candidate L6-only hit) prevents that, at the cost of demoting the LLM verdict to review rather than confirming absence.

## What would change my mind

A labeled replay of the 20 PR quotes (`00-baseline.md:13-21`) through the layered stack above, showing ≥ 80% precision at L0–L2 (`present`/`absent` without `ambiguous` on prose/date/code quotes) while `"x != y"` vs `"x == y"` and `$E=mc$` vs `$E=mc^2$` never register as candidate-absent, would flip this to **usable** without qualification.
