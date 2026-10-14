# 19 - Math-Fidelity-Auditor

**Verdict:** usable-with-conditions — inline `\(...\)` math facts catch relation flips and major operand swaps on the P4185 corpus, but pylatexenc folding plus lowercase collapses brace scope, case, and root index in ways olmOCR's geometry check would not.
**Confidence:** high

## Findings

- [CRITICAL] Brace-scope corruption is erased after folding: verified fact `\(x^{2k} \geq 0\)` and corrupted `\(x^2k \geq 0\)` both surface to `x^2k ≥0` and `_present_within` returns true (runtime probe, 2026-07-06). Evidence: `facts.py:173-181` (`_math_surface` = `textblock2unicode` + lowercase; pylatexenc drops `{2k}` braces). Impact: a conversion that scopes `2k` wrong (multiply-by-k vs even-power) false-passes Lane 3 while changing mathematical meaning.

- [HIGH] Lowercase at `facts.py:181` merges case-distinct math tokens after unicode fold: `X^T` and `x^t` both become `x^t`; `R`/`r` and `O(n)`/`o(n)` collide (runtime probe). Evidence: `facts.py:181`. Impact: variable-case and Big-O notation corruptions invisible to the math gate; olmOCR's KaTeX layout match would preserve symbol identity (`05-web.md` Q1: "KaTeX render -> relative symbol layout match").

- [HIGH] `textblock2unicode` only folds `$...$` and `\(...\)`; bare `\frac{a}{b}`, `\sqrt{x}`, `\begin{align}`, `$$...$$`, and `\[...\]` pass through unfolded (runtime probe). Evidence: `metrics.py:140`, `metrics.py:314-335`. Impact: markdown that loses delimiters but keeps backslash commands may false-pass against a delimited fact, or false-fail when both sides are bare; display math in P4185 (`P4185R0.expected.md:1155`, `\[a + b = c ...\]`) is outside the folding regex entirely.

- [HIGH] Nth-root index is lost when folding runs: `safe_latex_to_text(r'\sqrt{x}')` and `safe_latex_to_text(r'\sqrt[3]{x}')` both yield `√(x)`; fact `$\sqrt[3]{x}$` false-passes corrupted `$\sqrt{x}$` (runtime probe). Evidence: `metrics.py:274-296`, `metrics.py:314-335`. Impact: aligns with `05-web.md` Q5 (character-level / Unicode substitution metrics penalize Unicode math and correlate poorly with human judgment, r=0.34); our fold is exactly that substitution class.

- [MED] Complex inline environments are skipped, not folded: `_should_skip_inline_textblock_formula` returns true for `\begin{`, `\align`, `\\`, `&`, etc. (`metrics.py:299-311`). Evidence: `metrics.py:305-310`. Impact: `\begin{align} x &= 1 \\ y &= 2 \end{align}` stays literal LaTeX on the surface; olmOCR bench explicitly tests aligned/display math via geometry (`05-web.md` Q1, 3,385 math tests). Corpus gap confirmed in `00-baseline.md:79` ("no display-math/aligned-environment paper").

- [MED] P4185R0's four verified math facts are all inline `\(...\)` delimited; none assert the lone display-math block at line 1155 or the dozens of other inline formulas in the paper (e.g. `\tfrac{1}{2}mv^2` at `P4185R0.expected.md:478`). Evidence: `P4185R0.facts.jsonl:1-4`, `P4185R0.validation.md:41-44`. Impact: Lane 3 math coverage is four hand-picked identities on one paper, not display math or formula density; `00-baseline.md:54-55` counts 4 math / 9 verified facts total.

- [LOW] The ≥/≤ canary works: `\geq` → `≥`, `\leq` → `≤` after fold; scrambled `\(x^{2k} \leq 0\)` fails fact `math-even-power-nonneg` (runtime probe; CI at `test_comprehension_corpus.py:98-116`). Evidence: `test_comprehension_corpus.py:98-116`, `P4185R0.facts.jsonl:1`. Impact: relation-sign corruption is caught; canary strength is narrow (one flip, not brace/case/root classes).

- [LOW] Versus olmOCR we give up spatial symbol geometry and keep a cheap string surface: olmOCR renders KaTeX headless and compares relative bounding-box orientations (`05-web.md` Q1); whisker explicitly avoids KaTeX/Node (`facts.py:177-178`) and compares folded unicode substrings with `^`/`_`/`=` preserved (`facts.py:176-177`, `facts.py:351`). Quantified trade: we retain determinism and zero Node deps, but inherit the r=0.34 human-correlation ceiling of character/unicode formula metrics (`05-web.md` Q5) instead of layout-aware verification; empirically we detect `\frac{a}{b}` vs `\frac{b}{a}` (surfaces `a/b` vs `b/a`, runtime probe) but miss scope, case, and root-index errors olmOCR's geometry class targets.

## False-pass hypothesis

Corrupt `\(x^{2k} \geq 0\)` to `\(x^2k \geq 0\)` (drop braces so `2k` is no longer a single exponent). Both fold to `x^2k ≥0`; fact `math-even-power-nonneg` still passes (`facts.py:351`, runtime probe 2026-07-06). Semantic change (even-power non-negativity argument vs `(x^2)*k`) is invisible.

## False-fail hypothesis

A conversion emits bare `\frac{a}{b}` without `$`/`\(`` delimiters while the verified fact uses `\(\frac{a}{b}\)`. Fact side folds to `a/b`; document side stays `\frac{a}{b}` literal (`metrics.py:314-335`, runtime probe). Substring match fails despite equivalent math when delimiters are present on only one side.

## What would change my mind

A math fact corpus member with verified display-math or `\begin{align}` assertions that passes under correct conversion and fails under a layout-preserving corruption (e.g. swapped align rows), demonstrating the current surface catches an error olmOCR-style geometry would catch without adding KaTeX.
