# Opus Meta-Review A - Metric / Measurement Validity

**Scope:** re-verify every load-bearing measurement claim in personas 19, 20, 21,
22, 16, 06 against the actual code (`facts.py`, `metrics.py`), the committed
corpus (`corpus/*.facts.jsonl`, `*.expected.md`, `*.validation.md`), and the CI
gate (`test_comprehension_corpus.py`), NOT on the personas' word. Every runtime
number below was reproduced with the workspace venv against the committed
substrate at the baseline SHA. Probe scripts were temporary and deleted after
capture (numbers pasted inline).

**Method note:** two throwaway probes were run. One drove `_math_surface`,
`_present_within`, `_position_within`, `safe_latex_to_text` on constructed
formula pairs. One computed order-fact waypoint positions on the real
`P4182R0.expected.md` via `normalized_text` + `_position_within`. Grep counted
code fences / display-math / image refs in the corpus. Verdicts below are keyed
VERIFIED / DOWNGRADED / DROPPED.

---

## Claim 1 - Math brace-scope erasure (persona 19 CRITICAL) - **VERIFIED**

**Reproduced exactly.** `_math_surface(text) = _WS_RE.sub(" ",
textblock2unicode(text)).strip().lower()` (`facts.py:181`). Probe output:

```
good \(x^{2k} \geq 0\)  -> 'x^2k ≥0'
bad  \(x^2k \geq 0\)    -> 'x^2k ≥0'
surfaces equal? True
fact(good) present in doc(bad)? True
```

pylatexenc drops the `{2k}` braces during folding, so a correctly-scoped
`x^{2k}` (even power) and a mis-scoped `x^2k` (`(x^2)·k`) collapse to the *same*
surface string and `_present_within` returns True (`facts.py:239-241, 351`). The
KaTeX-geometry check olmOCR uses would keep `2k` as one superscript block
(`05-web.md` Q1). **The false-pass in persona 19's hypothesis is real.**

Corroborating sub-claims, all reproduced in the same probe:

- **Case merge (HIGH):** `$X^T$` and `$x^t$` both → `x^t`; equal. The trailing
  `.lower()` at `facts.py:181` erases variable case and Big-O case. VERIFIED.
- **Nth-root index loss (HIGH):** `safe_latex_to_text(r'\sqrt{x}')` and
  `safe_latex_to_text(r'\sqrt[3]{x}')` both → `√(x)`; fact `\sqrt[3]{x}` present
  in doc `\sqrt{x}` = True. VERIFIED (`metrics.py:274-296`).
- **Bare/display math not folded (HIGH):** `_INLINE_REG =
  r"\$(.*?)\$|\\\((.*?)\\\)"` (`metrics.py:140`) matches only `$...$` and
  `\(...\)`. Probe: bare `\frac{a}{b}` → `\frac{a}{b}` (literal); display
  `\[a + b = c\]` → `\[a + b = c\]` (literal). Display/aligned/`$$` math passes
  through the surface unfolded. VERIFIED.
- **Skip of complex inline envs (MED):** `_should_skip_inline_textblock_formula`
  returns True on `\begin{`, `\\`, `&`, unbalanced braces, len>128
  (`metrics.py:299-311`). VERIFIED by reading; consistent with the above.

**Counter-evidence that also survives (persona 19 LOW, as strengths):** the
surface is NOT uniformly blind. Probe: `\frac{a}{b}` → `a/b` vs `\frac{b}{a}` →
`b/a`, and `a/b` present in `b/a` = **False** (operand swap caught). Relation
canary: `\geq` → `≥`, `\leq` → `≤`, `\geq` not present in `\leq` doc
(`test_comprehension_corpus.py:98-116` reproduced). So the gate catches
relation-sign flips and fraction-operand swaps; it is blind specifically to
brace-scope, case, and root-index. Persona 19's calibration (`usable-with-
conditions`, not `garbage`) is warranted.

## Claim 2 - Reading-order permutability 46.1% (persona 20 CRITICAL) - **VERIFIED**

**Reproduced to the digit.** `order` facts require strictly increasing
`_position_within` hits across `fact.sequence` (`facts.py:353-365`), and
`_best_match` returns `haystack.find(needle)` (first occurrence) before any
fuzzy fallback (`facts.py:224`). Probe on the real `P4182R0.expected.md`
(normalized haystack = 18,671 chars):

```
wp1  0.9%   wp2  7.9%   wp3 13.1%   wp4 59.2%   wp5 92.6%
wp3->wp4: 8598 chars = 46.1%      wp1->wp5 span = 91.8%
```

The five verified anchors of `section-flow` (`P4182R0.facts.jsonl:6`) leave a
single 8,598-char zone (46.1% of the normalized document) between waypoints 3
and 4 that is *fully permutable*: any paragraph, table, or subsection inside it
can be arbitrarily reordered and the fact still passes. Persona 20's exact
figures (46.1%, 91.8%) are correct. **First-match-wins (finding #2) is also
code-confirmed** (`facts.py:224`); a repeated anchor phrase binds to its earliest
occurrence, so forward-referenced / Wording-section repeats can satisfy order at
the wrong locus. VERIFIED.

## Claim 3 - Fact-density gap vs olmOCR, ~5 tests/page (persona 21 HIGH) - **VERIFIED**

olmOCR-bench = 7,010 unit tests over 1,403 single-page PDFs (`05-web.md:18-20`);
7010 / 1403 = **4.997 ≈ 5.0 facts/page**. Corpus = **17 verified facts on 2
papers**: `P4182R0.facts.jsonl` = 8 lines (all `checked:verified`),
`P4185R0.facts.jsonl` = 9 lines (all `verified`) = 17. Arithmetic sound; the
"orders of magnitude below the adopted benchmark" headline holds.

Supporting zero-coverage-class claims, grep-verified against the corpus:

- **Fact schema has no code/xref/image type.** `FACT_TYPES = (present, absent,
  order, table, math)` (`facts.py:64`). VERIFIED.
- **Code-heavy class uncovered:** `P4182R0.expected.md` = **0** fenced lines;
  `P4185R0.expected.md` = **172** ```` ``` ```` fence lines (~86 code blocks),
  **0** code facts. Persona 21 said "~190 triple-backtick lines"; actual is 172
  (minor overcount, same order). Qualitative claim VERIFIED, the "190" figure
  DOWNGRADED to ~172.
- **Display math uncovered:** exactly **1** `\[` block in `P4185R0.expected.md`;
  all 4 math facts are inline `\(...\)` (`P4185R0.facts.jsonl:1-4`); the display
  block is unasserted. VERIFIED (matches persona 19 MED).
- **Image class uncovered:** **0** `![` refs across the corpus; no image fact
  type. VERIFIED.

## Claim 4 - Read-back: only run 3 byte-exact, no adversarial LLM control (persona 22 CRITICAL x2) - **VERIFIED**

- **Runs 1-2 never read the CI substrate.** `P4182R0.validation.md:45-47`: Run 1
  = "verbatim excerpt (tables + core sections)", Run 2 = "expanded (~330 lines
  ...)", Run 3 = "byte-exact, the subagent read the real committed
  `P4182R0.expected.md` directly". Two of three P4182 "8/8" anchors used
  experimenter-curated, un-archived excerpts, not the gate file. VERIFIED.
- **No adversarial LLM control.** `test_comprehension_corpus.py:77-96` and
  `:98-116` scramble a table cell / flip a relation then call `check_facts`, not
  an LLM. No corrupted markdown is ever shown to a reader model; 17/17 proves
  agreement in the *pass* direction only. VERIFIED.
- **Lexeme embedding (HIGH).** Q7 question row "GPU device code (CUDA, SYCL)"
  (`P4182R0.validation.md:38`) is the identical string to the fact `cell`
  (`P4182R0.facts.jsonl:7`); Q4 "Pigweed ... coroutines" ↔ fact text "Pigweed
  provides C++20 coroutines" (`.facts.jsonl:4`). The read-back questions are
  built from the fact strings, so substring retrieval can pass them without
  table-coordinate reasoning. VERIFIED (though note this is structural to any
  fact-derived QA, not a botch unique to this run).
- **Sample/contamination (HIGH):** n = 4 runs / 2 public WG21 papers / 17
  questions on 2026 frontier models is code/doc-confirmed; contamination and
  Wilson-bound arguments are sound statistical critique, not code claims. Kept as
  VERIFIED methodological limits, not code findings.

## Claim 5 - Is persona 22's "garbage" verdict proportionate? - **DOWNGRADED**

**The findings survive; the aggregate verdict does not.** Every underlying
finding in report 22 reproduced (Claim 4 above). But the `garbage` verdict is
disproportionate to what the artifact claims for itself:

- The read-back is explicitly, repeatedly self-scoped as a **one-time anchor**,
  not a population proof: "This is a one-time, manual empirical record. It is NOT
  a CI gate" (`P4182R0.validation.md:3-4`); "confirms ONCE, empirically ... After
  this anchor, the deterministic facts stand in for the LLM in CI"
  (`:13-16`); CLAUDE.md "validated ONCE, empirically and out of band ... the
  one-time anchor that justifies trusting the LLM-free gate."
- The docs disclaim the exact inference persona 22 attacks: they scope the
  conclusion "LLM-readable **for these facts**" and give determinism / cost /
  model-sovereignty as the stated reason it is not repeated or run in CI.
- Persona 16 (product-decision-skeptic) raises the *same* overreach ("read-back
  conclusions overreach their sample design", MED; "one-time read-backs license a
  narrow proxy claim", HIGH) and lands on **usable-with-conditions**. Same
  evidence, calibrated verdict. Persona 22's `garbage` is verdict inflation
  relative to 16.

There **is** a real, narrow overreach to preserve: the validation.md conclusion
sentence "the deterministic facts are a faithful proxy for what the LLM actually
recovers" is stated generally, and "the deterministic gate may stand in for the
LLM in CI" generalizes beyond the 17 authored facts on 2 easy papers. That is a
legitimate HIGH finding. But it is a finding about one over-broad sentence, not
grounds for a `garbage` rating of an artifact that honestly documents its own
weak runs and self-limits its scope. **DOWNGRADE:** persona 22's findings →
retained at HIGH; its verdict → `usable-with-conditions` (the read-back is a
correctly-scoped one-time anchor with one over-broad conclusion sentence to
tighten), consistent with persona 16.

## Persona 06 CRITICAL - Lane 3 is O(facts x doc_size), no memoization - **VERIFIED (asymptotic), DOWNGRADED (severity)**

**Code-confirmed.** `check_facts` loops facts calling `_evaluate(md, fact)`
(`facts.py:380-381`); inside, `present`/`absent` recompute `normalized_text(md)`
(`facts.py:343,347`), `math` recomputes `_math_surface(md)` (`facts.py:351`), and
`table` recomputes `_parse_pipe_tables(md)` (`facts.py:312`) - all over the whole
document, once per fact, with no cross-fact cache. The asymptotic claim is real.

**But the CRITICAL severity is an unmeasured projection.** "50 facts × 1 MB is
prohibitively slow / makes Lane 3 impractical" is contingent on a fact count and
document size that do not exist: the corpus is 2 papers, largest normalized
haystack 18,671 chars, max 9 facts. Persona 06's own "what would change my mind"
asks for a profile at 50 facts × 1 MB - which was never run. The inefficiency is
a genuine latent scaling defect and a real barrier to reaching olmOCR-scale fact
counts, but it is not an active failure at current scale. **DOWNGRADE:** verified
code finding, severity CRITICAL → HIGH-latent (real, unmeasured, blocks scale-up;
trivially fixable by memoizing the three whole-doc surfaces once per
`check_facts` call).

---

## Cluster summary - what survives

**Surface-collapse cluster (VERIFIED, load-bearing).** The math surface
`textblock2unicode → strip → lower` provably erases three semantic distinctions -
brace scope (`x^{2k}` = `x^2k`), variable case (`X^T` = `x^t`), and root index
(`\sqrt[3]{x}` = `\sqrt{x}`) - each reproduced as a live false-pass. It retains
relation signs and fraction-operand order (also reproduced), so the blindness is
specific, not total. This is the single most concrete, code-anchored measurement
gap in the stack: a formula corruption that changes mathematical meaning passes
the only comprehension lane that claims to test math.

**Coverage-power cluster (VERIFIED).** The measurement is real but under-powered:
17 verified facts on 2 hand-picked clean papers vs olmOCR's 5.0 facts/page over
1,403 PDFs; zero coverage for code (172 fence lines, 0 code facts), display math
(1 block, 0 facts), xref, and image classes; a 46.1%-permutable zone inside the
one order fact. The architecture is the right olmOCR pattern; the statistical
power to bound a ~200-paper fleet is absent.

**Empirical-anchor cluster (VERIFIED findings, DOWNGRADED verdict).** The
read-back's methodological limits (2/3 runs non-byte-exact, no adversarial LLM
control, fact-derived questions, n=17, contamination risk) all reproduce and are
legitimate HIGH-value caveats. The artifact's one over-broad conclusion sentence
deserves tightening. But `garbage` over-rates a doc that self-limits to a
one-time anchor; the calibrated verdict is `usable-with-conditions`.

**Performance cluster (VERIFIED asymptotic, DOWNGRADED severity).** The per-fact
whole-document re-normalization is code-confirmed and will block olmOCR-scale
fact counts, but is a latent, cheaply-fixable inefficiency at the current 2-paper
scale, not an active CRITICAL.

**Nothing was DROPPED.** Every claim checked reproduced against code/corpus. Two
severity/verdict inflations were DOWNGRADED (persona 22 `garbage`→conditions;
persona 06 CRITICAL→HIGH-latent) and one supporting figure was corrected
(persona 21 code fences "~190"→172).
