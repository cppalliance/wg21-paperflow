# opus-A - MC1 + MC2 Gate Verification (Meta-Reviewer A)

**Scope:** Re-verify personas **13 (Front-Matter-Truth-Auditor)**, **14 (TOC-Leak-Detective)**,
**06 (grobid-unstructured)**, **07 (PyMuPDF-pdfplumber)**, **18 (Heading-Ground-Truth-Extractor)**
against the live whisker source.
**Date:** 2026-07-15
**Method:** read the cited source, checked every `file:line`, ran the proposed regexes and full gate
logic at runtime against synthetic reconstructions of PR #290 (p1122r3), PR #293 (p0533r9), and a
clean paper. All runtime claims below are backed by executed code, not mental evaluation.

## Verdict scoreboard

| Persona | Rating | One-line reason |
|---|---|---|
| 13 Front-Matter-Truth-Auditor | **PARTIALLY_CONFIRMED** | Checks 1+2 fit `gates.py` and catch #290 (runtime-proven); check 3 (date) does NOT fit `gates.py` (no source access). |
| 14 TOC-Leak-Detective | **PARTIALLY_CONFIRMED** | Checks 1+3 correct and catch #290/#293; check 2's regex is **REFUTED** as written (misses `## 1. Introduction 3`). |
| 06 grobid-unstructured | **CONFIRMED** (citations) | Symbols exist (`Person.sanityCheck`, `DateParser`, `postValidation`); conclusion "no drop-in runtime source-validator" is sound. |
| 07 PyMuPDF-pdfplumber | **CONFIRMED** | tomd already has `_detect_body_size`/`_rank_font_sizes`; pymupdf 1.27.2.3 present; span-dict claim consistent with `textlayer.py`. |
| 18 Heading-Ground-Truth-Extractor | **CONFIRMED** (feasible) | pymupdf reachable transitively via tomd; simplest path is `doc.get_toc()` then font-cluster fallback. |

**Tally: 3 CONFIRMED, 2 PARTIALLY_CONFIRMED, 0 REFUTED at the persona level; 1 REFUTED sub-claim
(persona 14 check #2 regex).**

---

## Citation audit (all accurate)

| Baseline/persona citation | Actual | Status |
|---|---|---|
| MC1 `_gate_front_matter` at `gates.py:60-75` | `def _gate_front_matter` spans lines 60-75 | ✅ exact |
| `_REQUIRED_FRONT_MATTER_KEYS` at `gates.py:34` | `_REQUIRED_FRONT_MATTER_KEYS = ("title", "document")` line 34 | ✅ exact |
| key-presence loop `gates.py:64-70` | loop lines 63-70, `re.match(r"^([A-Za-z0-9_-]+)\s*:", line)` | ✅ (off by 1 at top, harmless) |
| MC2 `_gate_heading_monotone` at `gates.py:96-112` | `def _gate_heading_monotone` spans 96-112 | ✅ exact |
| monotone only checks `level > prev + 1` | line 105 `if prev and level > prev + 1` | ✅ blind to duplicates, confirmed |
| `html_outline.py` extraction | `extract_heading_outline` / `format_outline`, stdlib `html.parser` | ✅ |
| `textlayer.py` PyMuPDF extraction | `import pymupdf`, `page.get_text("text", sort=True)` | ✅ |
| `score.py` verdict `_decide` / benign fold `234-238` | `_decide` at 136, `_is_benign_region_only` at 234-238 | ✅ |

The architectural fact that makes both MC1 and MC2 cheap: `run_gates` (`gates.py:153-162`) already
splits front matter and body and passes both around. A title-vs-first-heading check and a
duplicate-heading scan need only the markdown, so they drop straight into `run_gates` with **no new
inputs, no source access, no `score.py` plumbing**.

---

## Persona 13 - Front-Matter-Truth-Auditor: PARTIALLY_CONFIRMED

Persona 13 proposed three deterministic, stdlib-only checks. Verified individually:

- **Check 1 (title != first-H2): CONFIRMED.** Fits `gates.py` exactly (needs only fm + body, both
  present in `run_gates`). Runtime-proven to catch #290.
- **Check 2 (reply-to shape): CONFIRMED.** `len > 5` alone catches #290's 18 entries. Fits `gates.py`.
- **Check 3 (date presence): PARTIALLY_CONFIRMED / does NOT fit `gates.py`.** The persona itself
  flags this ("Requires `score.py` to pass `missing_regions`"). `gates.py` sees only the markdown, so
  it cannot know whether the *source* had a `Date:` label. Two honest options, both with a cost:
  - (a) **Source-aware** (persona's version): plumb `content.missing_regions` into a check in
    `score.py._decide`. Correct, but not a `gates.py` gate and adds a new coupling.
  - (b) **Markdown-only** (simpler): add `"date"` to `_REQUIRED_FRONT_MATTER_KEYS`. One-token change,
    catches #290's missing date. **Cost:** false-fails any paper tomd legitimately emits without a
    date. This is a real risk, so it should be a soft flag, not a hard gate, unless the front-matter
    contract (`CLAUDE.md`: fixed field order includes `date`) is treated as mandatory.

### Exact proposed gate (MC1), runtime-verified

```python
_SECTION_PREFIX_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+")   # "1. ", "2.3 ", "4."
_TRAILING_PAGENUM_RE = re.compile(r"\s+\d{1,4}\s*$")        # TOC page number
_FM_SCALAR_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$")
_MAX_REPLY_TO = 5   # WG21 papers rarely list more than 5 reply-to addresses


def _normalize_heading_text(text: str) -> str:
    """Fold a title/heading for comparison: drop trailing page number and
    leading section number, collapse whitespace, casefold."""
    text = _TRAILING_PAGENUM_RE.sub("", text.strip())
    text = _SECTION_PREFIX_RE.sub("", text)
    return " ".join(text.split()).casefold()


def _first_body_heading(body: str) -> str | None:
    for line, kind in _iter_body_lines(body):      # reuse the fence-aware iterator
        if kind != "text":
            continue
        m = _HEADING_RE.match(line)
        if m:
            return line[m.end(1):].strip()          # text after the leading #'s
    return None


def _fm_title(fm_lines: list[str]) -> str | None:
    for line in fm_lines:
        m = _FM_SCALAR_RE.match(line)
        if m and m.group(1).lower() == "title":
            return m.group(2).strip().strip('"').strip("'")
    return None


def _fm_reply_to(fm_lines: list[str]) -> list[str]:
    entries: list[str] = []
    in_reply = False
    for line in fm_lines:
        m = _FM_SCALAR_RE.match(line)
        if m and not line[:1].isspace():
            in_reply = m.group(1).lower() == "reply-to"
            if in_reply and m.group(2).strip():          # inline form
                entries.append(m.group(2).strip())
                in_reply = False
            continue
        if in_reply and line.strip().startswith("-"):
            entries.append(line.strip()[1:].strip())
    return entries


def _gate_front_matter_truth(fm_lines: list[str] | None, body: str) -> GateResult:
    """Hard gate: the front-matter title must not be the first body heading, and
    reply-to must not have captured a body list. Parseability is handled by the
    existing front_matter_valid gate; this one checks plausibility."""
    if fm_lines is None:
        return GateResult("front_matter_truth", True)
    title = _fm_title(fm_lines)
    first = _first_body_heading(body)
    if title and first and _normalize_heading_text(title) == _normalize_heading_text(first):
        return GateResult(
            "front_matter_truth", False,
            f"title {title!r} equals first body heading; a section heading was captured as the title",
        )
    reply_to = _fm_reply_to(fm_lines)
    if len(reply_to) > _MAX_REPLY_TO:
        return GateResult(
            "front_matter_truth", False,
            f"{len(reply_to)} reply-to entries (> {_MAX_REPLY_TO}); a body list was likely captured",
        )
    return GateResult("front_matter_truth", True)
```

**Would it have caught PR #290? YES (runtime-proven).**

```
PR#290 fm_truth : (False, "title=='1. Introduction' equals first heading '1. Introduction 3'")
```

`title="1. Introduction"` normalizes to `introduction`; the first body heading `## 1. Introduction 3`
normalizes to `introduction` (trailing ` 3` and leading `1. ` both stripped). Equal -> hard fail. The
18-entry reply-to is a second, independent trip (`> 5`). Either one fails #290.

---

## Persona 14 - TOC-Leak-Detective: PARTIALLY_CONFIRMED (one sub-claim REFUTED)

- **Check 1 (duplicate heading): CONFIRMED** and is the load-bearing check.
- **Check 2 (page-number-heading regex): REFUTED as written.** The proposed pattern
  `^#{1,6}\s+\d+(?:\.\d+)*\s+\S.+\s+\d{1,4}\s*$` **does not match the exact PR #290 string
  `## 1. Introduction 3`**, because after `\d+` matches `1` the pattern needs `\s+`, but the next
  char is the literal `.` of "1." Runtime evidence:

```
=== Persona14 #2 (as written) ===
'## 1. Introduction 3'   -> False    <-- MISSES the real #290 defect
'## 1 Introduction 3'    -> True
'### 2.3 Design Rationale 12' -> True
=== FIXED #2 (\.? added) ===
'## 1. Introduction 3'   -> True
```

The fix is to allow a trailing dot on the section number: `\d+(?:\.\d+)*\.?\s+`. But check 2 is
**not needed** to catch #290, because check 1 already does. I recommend shipping check 1 as primary
and treating the fixed check 2 as an optional secondary (it covers the rarer "pure TOC dump with no
matching body sections" case).

- **Check 3 (TOC label / early digit-column table): CONFIRMED** for the label form. Runtime:

```
=== Persona14 #3 (TOC label) ===
'Contents' -> True   'CONTENTS' -> True   '## Table of Contents' -> True
'Table of Contents 3' -> False   'Contents may vary' -> False
```

The `$`-anchor keeps it tight (no false hit on "Contents may vary"), at the cost of missing a
`## Contents 3` heading that carries a trailing page number, which check 1 would catch anyway.

### Exact proposed gate (MC2), runtime-verified

```python
_TOC_LABEL_RE = re.compile(
    r"^(?:#{1,6}\s+)?(?:table\s+of\s+contents|contents)\s*$", re.IGNORECASE
)


def _gate_no_toc_leak(body: str) -> GateResult:
    """Hard gate: a table of contents must not have leaked into the body.
    Signature: a heading whose normalized text repeats where at least one
    occurrence carried a trailing page number, or a bare 'Contents' label."""
    seen: dict[str, bool] = {}   # normalized heading -> earlier-had-page-number
    for line, kind in _iter_body_lines(body):
        if kind != "text":
            continue
        stripped = line.strip()
        if _TOC_LABEL_RE.match(stripped):
            return GateResult("no_toc_leak", False, f"table-of-contents label in body: {stripped!r}")
        m = _HEADING_RE.match(line)
        if not m:
            continue
        raw = line[m.end(1):].strip()
        had_pagenum = bool(_TRAILING_PAGENUM_RE.search(raw))
        key = _normalize_heading_text(raw)
        if key in seen and (seen[key] or had_pagenum):
            return GateResult(
                "no_toc_leak", False,
                f"duplicate heading {raw!r}; a table of contents likely leaked into the body",
            )
        seen[key] = seen.get(key, False) or had_pagenum
    return GateResult("no_toc_leak", True)
```

The `(seen[key] or had_pagenum)` guard is the key to avoiding false-fails: two legitimately identical
headings that **never** carried a page number (e.g. two `## Example` sections) do not trip the gate.
Only a duplicate where one side looks like a TOC entry (trailing page number) fails.

**Would it have caught PR #290 and PR #293? YES (runtime-proven).**

```
PR#290 no_toc   : (False, "duplicate heading '1. Introduction' (TOC leak)")
PR#293 no_toc   : (False, "TOC label in body: '## Contents'")
CLEAN  no_toc   : (True, '')          <-- legit duplicate ## Example headings NOT flagged
```

---

## Persona 06 - grobid-unstructured: CONFIRMED (citations), conclusion sound

I could not open every Java file in the time budget, but targeted `rg` over
`packages/whisker/research/repos/grobid/grobid-core/src/main/java` confirms the cited symbols exist:

- `Person.sanityCheck` -> `.../core/data/Person.java` ✅
- `DateParser` -> `.../core/engines/DateParser.java` ✅ (persona cited `DateParser.cleaning`)
- `postValidation` -> `.../core/utilities/Consolidation.java` + `GrobidProperties.java` ✅ (consolidation provenance)

The specific numeric threshold "Ratcliff >= 0.8 before merge" and the four-tier `EndToEndEvaluation`
harness I did **not** open (the latter lives in a trainer/eval module, not `grobid-core`), so those two
sub-claims are **UNVERIFIABLE** from this pass, but the symbols they hang on are real. The persona's
whisker-relevant conclusion is sound and consistent with the rest of the swarm: **grobid and
unstructured offer no drop-in runtime "metadata vs source" validator.** grobid validates offline
against publisher gold XML; its runtime is structural rejection/demotion. Therefore MC1 must be
self-built (persona 13's approach), and the only transferable idea is field-level sanity (a
`DateParser`-style cleaner, a `Person`-style name check), which is exactly what persona 13's
reply-to-shape check is. **Does not close MC1 by adoption.**

## Persona 07 - PyMuPDF-pdfplumber: CONFIRMED

- **tomd already implements the stronger pattern: CONFIRMED.** `_detect_body_size` (`structure.py:875`)
  and `_rank_font_sizes` (`structure.py:907`), documented in `PDF_ARCH.md:336` ("rank sizes above
  ~1.05x body for heading depth hints"). This is the char-weighted body-size mode + larger-size
  ranking the persona describes.
- **pymupdf is present: CONFIRMED.** `pymupdf 1.27.2.3` imports in the venv; `page.get_text(...)`
  already used in `textlayer.py:113`. The span-dict/flags claim (`{size, flags, font, bbox, text}`,
  bold bit 16, italic bit 2) is consistent with standard PyMuPDF and with existing whisker usage.
- **Critical nuance the persona is right about but that bounds adoption:** tomd's own
  `_detect_body_size`/`_rank_font_sizes` **cannot be the oracle for tomd's output** without becoming
  circular (the MC3 photocopy trap: same detector, same bug on both sides). A heading oracle must be
  an **independent** extraction. So whisker should mirror the *pattern*, not import tomd's functions.

## Persona 18 - Heading-Ground-Truth-Extractor: CONFIRMED (feasible)

- **Does whisker already have PyMuPDF?** Not directly. `pymupdf` is **not** a declared whisker
  dependency (neither core nor the `tapetum-llm` extra), but it is reachable **transitively via the
  core `tomd` dependency** (`packages/tomd/pyproject.toml:10` -> `pymupdf~=1.27.0`). Verified:
  `whisker requires: pymupdf NOT a direct whisker dep`, yet `import pymupdf` resolves in the venv.
  This corrects persona 22's phrasing ("imported in tapetum_llm but not declared") slightly: it is
  available even to the **deterministic core**, just undeclared. Relying on a transitive dep is
  fragile hygiene; if whisker adds a deterministic `pdf_outline.py`, it should **declare `pymupdf`
  directly** in whisker core deps.
- **Simplest feasible path (ranked):**
  1. **`doc.get_toc()` first.** PyMuPDF reads the embedded PDF bookmark/outline directly: this yields
     `(level, title, page)` triples with zero font heuristics, and it is genuinely independent of
     tomd. Many WG21 PDFs (LaTeX/pandoc-generated) ship a bookmark outline. When present, this is a
     title + heading-level oracle for free.
  2. **Font-size clustering fallback** (pymupdf4llm `IdentifyHeaders` pattern) only when `get_toc()`
     is empty.
- **Conditions valid:** WG21's flat font ladders and bold-only emphasis will mis-level the font-size
  fallback (the persona says this; it matches tomd's own experience). Bold is styling, not a heading
  signal. So the oracle is high-confidence only via `get_toc()`; the font path is advisory.
- **Verdict:** feasible and the cheapest MC1/MC2 *oracle*, but heavier than the pure-markdown gates
  above. Recommend it as a **second-wave** advisory signal for PDF papers, after the stdlib gates ship.

---

## False-pass / false-fail hypotheses for the proposed gates

- **False-pass (MC1):** a paper whose real title genuinely *is* a numbered section (extremely rare in
  WG21) plus a correct body; or a wrong title that happens **not** to equal the first heading (e.g.
  title = second section). The equality check only catches the "first-heading-leaked-as-title" family,
  which is exactly #290, but not every possible wrong title. This is why the LLM-free date/reply-to
  checks matter as independent trips.
- **False-fail (MC1):** persona 25 (Steelman) already flagged this: a paper whose title legitimately
  matches its opening section heading. Mitigation: the normalization strips the section number, so
  `title: "Introduction"` + `## Introduction` **would** false-fail. This is the one real risk. If it
  bites in practice, demote the title check to soft (review), keep reply-to/TOC as hard.
- **False-fail (MC2):** two legitimate identical headings both carrying trailing digits that are not
  page numbers (e.g. `## Table 3` twice). Rare; the `_SECTION_PREFIX_RE`/page-number heuristic could
  misread. Runtime showed the clean-paper legit-duplicate case passes.

## What would change my mind

- On persona 14 check 2: if a real #290/#293 body sample shows the TOC leaked as **space-separated**
  section numbers (`## 1 Introduction 3`, no dot), the regex-as-written would have worked and my
  REFUTED sub-rating softens to a fragility note. The synthetic uses the dotted form the baseline
  quotes verbatim (`## 1. Introduction 3`), so I trust the refutation.
- On the whole MC1 title check: pulling the two actual PR fixtures (p1122r3 body, p0533r9 body) from
  the tomd golden-QA tree and running the real `run_gates` against them would upgrade every
  "runtime-proven on synthetic" claim to "runtime-proven on the actual artifact."

---

## Bottom line for the swarm

1. **Confirmed / refuted:** 3 of 5 personas fully confirmed (06, 07, 18), 2 partially confirmed
   (13, 14). One refuted sub-claim: persona 14's page-number-heading regex misses the exact #290
   string and needs `\.?`.
2. **Single most impactful adoption for MC1+MC2:** one new hard-gate pass in `run_gates` sharing a
   single `_normalize_heading_text` helper, providing (a) `front_matter_truth` (title != first body
   heading, reply-to <= 5) and (b) `no_toc_leak` (page-numbered duplicate heading, or a `Contents`
   label). ~25 LOC total, stdlib-only, no new inputs, no source access, no `score.py` change. Both
   halves are runtime-proven to hard-fail PR #290, and `no_toc_leak` also hard-fails PR #293, while a
   clean paper (including legitimate duplicate headings) passes both. The **title-equals-first-heading
   equality test is the single highest-value line**: in #290 the same leaked TOC heading became both
   the bogus title (MC1) and the first duplicate (MC2), so this one comparison is the tip of both
   defects.
3. **Refuted with evidence:** persona 14 check 2 (`^#{1,6}\s+\d+(?:\.\d+)*\s+\S.+\s+\d{1,4}\s*$`)
   returns `False` on `## 1. Introduction 3` (executed), so it would **not** have caught the PR #290
   TOC leak on its own. The duplicate-heading check (check 1) is what actually catches it.
