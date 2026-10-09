# C15 Metric Validity

**Role**: Audit whether NID, TEDS, MHS, content_recall, and unigram_coverage measure what they claim, using live metrology canaries as the primary evidence class.
**Audited state**: whisker 0.5.0, working tree, manifest b9ad8ab0a464aaaf030bfb9a9576bdeed986f6510b83dbd87945bdd7fe68f771.
**Gates**: G4 (measurement validity, PROPOSED), D4 (per-axis null-eligibility, PROPOSED).

## 1. Scope

This is a construct-validity claim, not a bug report: for each metric,
determine which classes of corruption its own definition makes it capable of
representing, and which classes its definition makes it structurally
incapable of representing, independent of threshold placement (C14). The
live canaries (ledger E17, E18) are four real mutations of one document run
against both lanes this run; they are treated as the primary evidence, with
`metrics.py` read to explain WHY each result occurred, not merely to
document that the code matches a published algorithm (Auditv2's frame).

## 2. Commands and Exits

| Evidence | Command / source | Result |
|---|---|---|
| E1 | `uv run --package whisker pytest packages/whisker/tests -q --tb=line` | exit 1: 3 failed, 1784 passed, 8 skipped, 3 xfailed |
| E17 | `rt4_canaries.py`, four mutations of one 25157-char, 9-H2-section ideal | control + C1-C4, det verdict / `unigram_coverage` / LLM / fused per row |
| E18 | Same driver, C4 detail table | `text_nid`, `content_recall`, `unigram_coverage` numerically identical to control; LLM reasoning byte-identical |
| — | `packages/whisker/src/whisker/metrics.py` read | full file, 698 lines |
| — | `packages/tomd/src/tomd/lib/check_content.py` read (relevant sections) | `_multiset_coverage`, `unigram_coverage` computation |

## 3. Current Evidence

### 3.1 What each metric is actually computed on

- **`text_nid(a, b)`** (`metrics.py:347-354`): `1.0 - normalized_edit_distance(
  _normalize_text(a), _normalize_text(b))`. `_normalize_text` (`metrics.py:
  84-85`) is whitespace-collapse ONLY (`_WS_RE.sub(" ", text).strip()`). In
  every call site actually exercised by score.py and pdf_judge.py, the
  caller pre-normalizes both arguments with `normalized_text` (`metrics.py:
  342-344`, `= clean_string(textblock2unicode(text))`) BEFORE calling
  `text_nid` (`score.py:272`: `text_nid(normalized_text(md_text),
  normalized_text(reference_md))`; `pdf_judge.py:652`: `text_nid(
  normalized_text(pdf_text), normalized_text(tomd_md))`). So the character
  stream that actually reaches the Levenshtein distance has already had
  `clean_string`'s filter applied: `_CLEAN_KEEP_RE = re.compile(r"[^\w\u4e00-
  \u9fff]")` (`metrics.py:115`) strips every character that is not a word
  character or CJK. Punctuation, brackets, operators, and all markdown
  syntax are gone before the edit distance is computed, not merely
  down-weighted.
- **`content_recall(candidate, reference)`** (`metrics.py:376-393`): multiset
  recall over `content_tokens`, which is `_CONTENT_TOKEN_RE.findall(
  textblock2unicode(text).lower())` with `_CONTENT_TOKEN_RE = re.compile(
  r"\w+", re.UNICODE)` (`metrics.py:359-373`). `\w+` matches only word
  characters; it never captures a punctuation or symbol character as part
  of a token, and it never captures punctuation as a token in its own
  right. The recall is computed over the resulting multiset with `Counter`
  equality (order and position discarded entirely by construction, per
  the docstring: "Order... are NOT penalized").
- **`unigram_coverage`** (`tomd/lib/check_content.py:619`, called from
  `score.py` transitively via `check_paper_content`):
  `_multiset_coverage(src_tokens, md_tokens)`, a fraction-present multiset
  recall over word-level tokens from `_extract_markdown_stream`, the same
  family of construct as `content_recall` (order-invariant multiset
  recall), computed source-vs-candidate rather than reference-vs-candidate.
- **`teds`** and **`mhs`** operate on structurally different surfaces (an
  HTML table DOM and a heading-only AST respectively, `metrics.py:396-555`
  and `558-697`) and are unaffected by prose-level corruption by
  construction; they were not exercised by the canaries (none of C1-C4
  touch a table's tag/colspan/rowspan structure or the heading tree).

### 3.2 The canaries, read against the definitions above

Ledger E17, base document 25157 chars, 9 H2 sections:

| Canary | Mutation | Token-preserving? | `unigram_coverage` | Why, per 3.1 |
|---|---|---|---|---|
| control | none | — | 0.9542 | baseline |
| C1 | delete `## 3. Platforms` (11757 chars, 46.7%) | No | 0.5021 | ~half the word multiset is genuinely absent from the candidate; a multiset-recall metric is exactly the right instrument for a deletion, and reports it correctly |
| C2 | reverse section order | Yes | 0.9542 (unchanged) | a multiset recall metric is invariant to permutation of its input by definition; every token that was present still is, just relocated |
| C3 | swap two table cell values | Yes | 0.9542 (unchanged) | a swap of two existing values is a permutation of the same multiset (the two values simply trade positions), so a multiset-recall metric cannot distinguish it from the identity permutation |
| C4 | corrupt 14 `<memory_resource>` -> `<memory_resource<` | Yes, at the word-token level | 0.9542 (unchanged) | `\w+` never included the angle brackets in the first place; the word token `memory_resource` is byte-identical before and after this specific corruption, so the multiset is literally unchanged, not merely insensitive to it |

C1 confirms the metric class works exactly as designed for its designed
target (content loss). C2, C3, and C4 are not three instances of the same
finding: C2 and C3 are corruptions the multiset-recall CONSTRUCT is
mathematically invariant to (any permutation of an unchanged multiset scores
identically, by definition of "multiset"). C4 is a corruption that never
entered the multiset's alphabet at all, because the tokenizer (`\w+`) and
the text normalizer (`_CLEAN_KEEP_RE`) both discard the exact character
class (`<`, `>`) the mutation touched, before any comparison logic runs.

### 3.3 C4's triple-identical result, quantified (E18)

| | control | C4 |
|---|---|---|
| `text_nid` | 0.8645 | 0.8645 |
| `content_recall` | 0.9697 | 0.9697 |
| `unigram_coverage` | 0.9542 | 0.9542 |
| model reasoning | "No content loss, corruption, or reordering found..." | byte-identical string |

All three deterministic axes report the SAME value to at least four decimal
places, not merely "close." Per 3.1, this is not measurement noise falling
below a rounding threshold: `text_nid`'s input stream and `content_recall`'s
tokenizer both structurally exclude `<`/`>` before any distance or set
computation runs, so the two markdown strings (14 occurrences of
`<memory_resource>` vs `<memory_resource<`) reduce to literally the same
normalized string and the literally same token multiset. Zero difference,
not small difference, is the mathematically expected output of feeding
these two inputs through these three functions as defined. The LLM's
reasoning being byte-identical is a separate fact (adjudicated under C16)
but is corroborating: nothing in either deterministic signal set the model
apart from the control to react to, either.

### 3.4 The router's keyword list independently cannot see C4's corruption class

`source_router.py`'s `_CPP_KEYWORDS` (`textlayer.py:79-82` and
`source_router.py:45-48`) is a fixed C++ keyword list (`constexpr`,
`template`, `struct`, `class`, `enum`, `auto`, `concept`, `requires`,
`noexcept`, `void`, `int`, `float`, `double`, `char`). `memory_resource` is
not in that list, so `route_pdf_units`'s `TOKEN_DELTA_THRESHOLD`-gated
keyword-count check (`source_router.py:184-207`) would not flag this
corruption class even for a keyword it did track, because (per 3.1) the
corrupted identifier's word-token form is unchanged; the router shares the
same `\w+`-family blindness as the metrics it is meant to supplement.

### 3.5 What the deterministic surface CAN represent, stated affirmatively

- Whole-token deletion or insertion at any scale (C1 proves this; the
  content-recall family is precisely a set/multiset-difference detector).
- Reordering of tokens that changes the SET of adjacent-token bigrams if a
  shingle/order-sensitive metric is also consulted; whisker's own `coverage`
  (5-gram shingle) and `drift` fields exist for this reason
  (`constants.py:20-38` comments), though they are explicitly non-gating
  (`score.py` `_decide` never reads them as hard signals; `whisker/CLAUDE.md`
  "Verdict model").
- Any corruption that changes at least one `\w+`-matched token's character
  content (a misspelling, a digit change inside a word, a case change if a
  case-sensitive comparison is used downstream).

### 3.6 What the deterministic surface (`text_nid`, `content_recall`,
`unigram_coverage`) provably CANNOT represent, by construction

- **Any permutation of existing word tokens** (reordering sections,
  reordering table rows, swapping two cell values that are drawn from the
  document's own vocabulary), because multiset equality is permutation-
  invariant by mathematical definition. This is C2 and C3.
- **Any corruption confined entirely to non-word characters**: punctuation,
  brackets, mathematical/logical operators, whitespace-adjacent symbols.
  `\w+` never tokenizes these at all, and `_CLEAN_KEEP_RE` deletes them
  before `text_nid`'s edit distance runs. This is C4. The same blind spot
  applies to any single-character punctuation flip that changes meaning
  without changing a word (a dropped `!` in `!=`, a `<` becoming a `<=`
  where the extra character is itself punctuation, a comma vs. period).
- **Semantic relation flips expressed purely through non-word symbols**
  (e.g. `x >= y` vs `x <= y` would survive `\w+` tokenization identically
  since `>=`/`<=` are stripped, leaving only `x`, `y`; whisker's own
  `facts.py` documentation independently acknowledges a version of this for
  math facts, describing a "raw" surface mode specifically because the
  normalized surface cannot distinguish operators, though that mode lives
  in Lane 3 comprehension facts, not in the bench/verdict metrics audited
  here).

### 3.7 Construct separation and null-eligibility, unchanged from Auditv2

`teds`, `mhs`, `text_nid`, and `content_recall` remain a faithful PubTabNet
port, an APTED-backed heading-tree comparison, an OmniDocBench-normalizer
edit distance, and a standard multiset recall respectively, matching their
published definitions (`metrics.py:396-555`, `558-697`, `347-354`, `376-
393`, all re-read this pass and structurally unchanged from Auditv2 §3.1-
3.4). `has_headings` (`metrics.py:671-679`) still returns `False` for
heading-free documents rather than a synthetic 1.0, and the zero-
denominator TEDS guard (`metrics.py:510-514`) is still the sole documented
adaptation from the verbatim port. None of this is disputed; the delta
this pass adds is that "correctly implements its definition" and "the
definition covers the corruption space a reader assumes it does" are
different claims, and the canaries test the second one.

## 4. Findings

| # | Finding | Severity | Confidence |
|---|---|---|---|
| F1 | `text_nid`, `content_recall`, and `unigram_coverage` are all members of the same construct family (order-invariant, word-character-only, multiset-style comparison), not three independent lines of defense against corruption, despite being reported as three separate fields | HIGH | HIGH |
| F2 | Token-preserving reordering (C2: section order; C3: table-cell-value swap) is mathematically invisible to all three deterministic metrics by definition, not by miscalibration; no threshold adjustment (C14) can fix this, only a different metric construct (e.g. block-matched or position-aware scoring) can | HIGH | HIGH |
| F3 | Corruption confined to non-word characters (C4: 14 `<memory_resource>` -> `<memory_resource<` mangles) produces numerically IDENTICAL values on all three deterministic metrics vs. an untouched control, confirmed to 4 decimal places (E18); this is a structural alphabet exclusion (`\w+` tokenizer, `_CLEAN_KEEP_RE` normalizer), not measurement noise | HIGH | HIGH |
| F4 | The source-aware risk router (`source_router.py`) shares the same `\w+`-family blindness for its keyword-delta signal and additionally does not track the specific identifier (`memory_resource`) involved in C4, so it provides no independent backstop for this corruption class either | MEDIUM | HIGH |
| F5 | `teds`/`mhs` remain faithful, unrelated-construct ports (table DOM tree-edit, heading AST tree-edit) and were not exercised by any of the four canaries, so this run adds no new evidence about their validity beyond Auditv2's code-level confirmation | INFO | MEDIUM |
| F6 | `clean_string` not stripping YAML front-matter keys (Auditv2 F5) is unchanged and orthogonal to F2/F3; not re-measured this pass | INFO | LOW |

## 5. False-Pass Hypothesis

**Could a metric report high similarity when the content is actually
different, beyond the cases Auditv2 already enumerated?** Auditv2's §5
addressed TEDS-on-prose, MHS-on-flat-documents, and duplicated-token
inflation as hypothetical failure modes with code-level falsification. This
run replaces two of those hypotheticals with measured fact: C2 and C3 are
not "could a converter duplicate tokens," they are "an entire section
reorder or a table-cell swap scores as if nothing happened," observed
directly (E17), and C4 is not "a metric might be insensitive," it is
"three independently-implemented metrics returned the identical decimal
value because they share a tokenizer alphabet that excludes the corrupted
characters" (E18). The hypothesis is no longer counterfactual for these
three classes; it is confirmed.

**Is this a bug, or a scope limitation of the metric family?** The report
takes no position (per task instruction, this is a validity claim, not a
bug report). What is established is the SHAPE of the limitation: it is not
that thresholds are wrong (C14), and it is not that any single metric has
an implementation defect relative to its own published algorithm (§3.7);
it is that three of the five metrics named in this claim's scope
(`text_nid`, `content_recall`, `unigram_coverage`) share one construct
(order- and punctuation-invariant multiset recall) and therefore share one
blind spot, so a reader who sees three green fields may reasonably but
incorrectly infer three independent confirmations.

## 6. Gate/Dimension Mapping (PROPOSED)

| Gate | Dimension | Status (PROPOSED) |
|---|---|---|
| G4: Measurement validity | Content-loss detection (deletion/insertion) | PROPOSED SOUND (F1's construct family does this by design; corroborated by C1) |
| G4: Measurement validity | Permutation / reorder detection | PROPOSED OUT OF SCOPE for `text_nid`/`content_recall`/`unigram_coverage` by construction (F2) |
| G4: Measurement validity | Non-word-character corruption detection | PROPOSED OUT OF SCOPE for the same three metrics by construction (F3) |
| D4: Per-axis null-eligibility | `teds`/`mhs` construct separation | PROPOSED PASS, unchanged from Auditv2 (F5) |

## 7. Limitations

- The four canaries are all mutations of one document (`p4182r0`'s ideal,
  per C13 §3.3); this report does not generalize F2/F3 beyond the
  demonstrated mechanism to claim a measured false-negative rate across the
  corpus. The mechanism (tokenizer alphabet, permutation invariance) is a
  property of the code read in `metrics.py`, independent of which document
  it is demonstrated on, but the specific decimal values in §3.2-3.3 are
  single-document measurements.
- `coverage` and `drift` (the order-sensitive shingle metrics reported
  alongside `unigram_coverage`, per `constants.py:20-38`) were not measured
  by the canaries in the ledger; whether they WOULD catch C2's reorder is
  not evidenced here, only that they are documented as non-gating even if
  they did (`score.py` `_decide`).
- Whether `text_nid`'s whitespace-only internal `_normalize_text` (as
  opposed to the caller-applied `normalized_text`) would behave differently
  if some future call site passed raw, un-`clean_string`-filtered text was
  not tested; this report only traces the call sites actually exercised by
  `score.py` and `pdf_judge.py`.
- `grits_con` (mentioned in Auditv2 §7 as advisory, living in `bench.py`)
  was not re-examined against the canaries; C3's table-cell swap is exactly
  the corruption class GriTS-Con's cell-content F1 is documented to target,
  but no canary evidence exists either way this run.

## 8. Conclusion

The four live canaries convert what Auditv2 could only pose as hypotheses
into measured fact. `text_nid`, `content_recall`, and `unigram_coverage`
correctly and sensitively detect outright content deletion (C1: 46.7%
deletion drives `unigram_coverage` from 0.9542 to 0.5021, both lanes
correctly fail it). The same three metrics are, by the mathematics of their
own definitions, incapable of representing two entire corruption classes:
token-preserving reordering (section permutation, cell-value swaps; C2, C3)
and any corruption confined to characters outside their shared `\w+` /
`_CLEAN_KEEP_RE` alphabet (C4's angle-bracket corruption, measured
numerically IDENTICAL to the control on all three axes to four decimal
places). This is not a calibration problem and not an implementation bug
relative to each metric's published algorithm; it is the scope of the
construct itself. `teds` and `mhs` are unaffected because they operate on
different surfaces entirely, but none of the four canaries exercised them,
so this run adds no new evidence for or against their validity beyond
Auditv2's code-level confirmation. No verdict is rendered on whether this
scope is acceptable for the tool's stated purpose.

## 9. Delta vs Auditv2

Auditv2's C15 (HEAD 51cb704, no runtime evidence available for this claim
either) verified all four metrics against their published algorithms via
code inspection alone and rendered "Gate verdict: PASS" (Auditv2 §8),
supported by hypothetical false-pass scenarios in §5 that were falsified by
reading the code, not by running it against an adversarial input. This
report's central shift is evidentiary class: every finding in §3.2-3.4 is a
live measurement (E17, E18) against real mutations of a real document,
where Auditv2 had none. Two of Auditv2's own findings are directly
sharpened by this: Auditv2 F3 ("content_recall is correctly independent of
text_nid... A dropped section affects content_recall directly but may be
hidden by text_nid if the remaining text is long enough") described a
theoretical asymmetry between the two metrics; this run's C4 shows the two
metrics are not independent in the relevant sense at all, they are
numerically IDENTICAL on the same corrupted input because they share a
tokenizer/normalizer alphabet, a stronger and different claim than "one
metric might mask what the other measures." Auditv2 F5 (front-matter
tokens in `clean_string`) is untouched and carried forward as INFO/LOW.
This report also removes "PASS" framing entirely per this batch's hard
rule against final verdicts; Auditv2's Gate verdict line is not repeated
or updated, only superseded by the PROPOSED mapping in §6.
