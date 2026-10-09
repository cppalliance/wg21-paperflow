# Opus Meta-Reviewer D: Boundary, Tests, Tables & Fold

**Scope:** Re-verify personas 22 (Whisker-Boundary-Guardian), 24 (Test-Suite-Auditor),
19 (Table-Separator-Robustness), 20 (Gate-Fold-Skeptic), 21 (Prior-Research-Archaeologist)
against the actual `packages/whisker` source.
**Date:** 2026-07-15
**Method:** Read every cited file/line, grep for imports/tests, trace the regex change against
the committed test corpus.

## Verdict tally

| Persona | Claim | Rating |
|---|---|---|
| 19 | `_TABLE_SEP_RE` identical in both files, `-{2,}`; `-+` fix breaks no test | **CONFIRMED** |
| 20 | `_is_benign_region_only` only matches `"misaligned region"`; ref_nid stays review | **CONFIRMED** |
| 21 | LLM lanes implemented; MC1-MC5 det fixes documented but NOT implemented | **CONFIRMED** |
| 22 | PyMuPDF imported in `tapetum_llm/` but not declared in whisker | **CONFIRMED** (+nuance) |
| 24 | `test_tables.py` does not exist; `parse_pipe_tables`/single-dash untested | **CONFIRMED** |

**5 confirmed, 0 refuted, 0 unverifiable.** One nuance recorded under persona 22.

---

## Persona 19 — Table-Separator-Robustness — CONFIRMED

**Claim A: both regexes identical, using `-{2,}`.**

```36:36:packages/whisker/src/whisker/tables.py
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
```

```132:132:packages/whisker/src/whisker/gates.py
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
```

Byte-for-byte identical. Both require `-{2,}` (two or more hyphens per delimiter cell).
GFM §4.10 requires **one or more** hyphens, so `| - | - |` (single hyphen per column) is a
valid GFM delimiter row that BOTH scanners currently miss. **CONFIRMED.** The duplication is
also a DRY defect: the persona's "export one shared constant from `tables.py`" is the correct
fix (gates.py should import it).

**Claim B: changing `-{2,}` to `-+` breaks no existing test.** **CONFIRMED.**

`-+` (one-or-more) is a strict superset of `-{2,}` (two-or-more): every string the old regex
matched, the new one still matches. Every committed test separator uses >= 2 dashes:

- `test_gates.py:72` `|-----|---|`, `:78` `|---|`, `:93` `|-------|-------|`
- `test_facts.py:26` `|------------|--------|-------|`, plus `|---|---|`, `|---------|-------|`
- `test_bench.py:20` `|---|---|`

None assert that a single-dash line is NOT a table, so nothing regresses. The one "negative"
test, `test_thematic_break_is_not_an_empty_table` (`test_gates.py:83-87`), uses a bare `---`
with **no pipe**; it is excluded by the pipe guard (`"|" not in line` at `gates.py:142`,
`"|" in lines[i+1]` at `tables.py:71`), which the regex change does not touch. Traced `|-|`
against the `-+` variant by hand: leading `\|?` eats the first pipe, `-+` eats the dash, the
trailing `\|?` eats the last pipe → matches. Single-column single-dash works.

**Residual risk (not a test break, a runtime regression, flagged by persona 25):** `-+`
makes pipe-adjacent prose containing a lone `-` cell easier to misread as a table. That is a
real-paper concern, not a test-corpus concern, and the persona already prescribes the
mitigation (the `|`-in-line guard stays). Recommend adding a parametrized single-dash case to
a new `test_tables.py` when landing the fix (see persona 24).

---

## Persona 20 — Gate-Fold-Skeptic — CONFIRMED

**Claim: `_is_benign_region_only` requires every soft flag to contain `"misaligned region"`,
so an advisory `ref_nid` flag cannot fold a paper to pass.**

```234:238:packages/whisker/src/whisker/score.py
def _is_benign_region_only(soft: list[str], unigram_coverage: float) -> bool:
    """True when all soft flags are region flags and coverage is high enough."""
    if unigram_coverage < C.REGION_BENIGN_UNIGRAM_FLOOR:
        return False
    return all("misaligned region" in f for f in soft)
```

The fold guard is `all("misaligned region" in f ...)`. The region flag string is
`f"{region_total} misaligned region(s)"` (`score.py:191`) — it contains the sentinel. The
advisory oracle flag is:

```202:203:packages/whisker/src/whisker/score.py
        if ref_nid < C.REF_NID_ADVISORY_EDGE:
            soft.append(f"reference text agreement {ref_nid:.3f} low (advisory)")
```

That string does NOT contain `"misaligned region"`, so a paper whose soft flags include the
advisory `ref_nid` fails `_is_benign_region_only` and falls through to `return VERDICT_REVIEW`
(`score.py:229-230`). **CONFIRMED**: the p3953r0 example correctly stays `review`; the fold is
intentionally narrow and the current behavior is by design, not a bug. `REGION_BENIGN_UNIGRAM_FLOOR = 0.95`
(`constants.py:54`) and `REF_NID_ADVISORY_EDGE = 0.85` (`constants.py:94`) match the persona's
numbers.

The persona's *recommendation* (demote `ref_nid` to report-only like `ref_teds`/`ref_mhs`
until corpus-calibrated) is a design proposal, not a factual claim; the factual analysis of
current behavior is exact. "Never fold ideal-panel flags" is also correct: ideal flags use the
string `f"ideal {axis} ... (advisory)"` (`score.py:215`), which likewise never matches the
sentinel and so can never be folded.

---

## Persona 21 — Prior-Research-Archaeologist — CONFIRMED

**Claim A: hybrid-llm-scoring and per-page-judging are largely implemented.** CONFIRMED.
`tapetum_llm/fusion.py` (asymmetric fusion) and `tapetum_llm/pdf_judge.py` (`screen_pages`)
both exist in the tree (also asserted in `00-baseline.md:99-100`).

**Claim B: MC1-MC5 deterministic fixes documented but NOT implemented.** CONFIRMED by direct
source read:

- **MC1 front-matter truth:** `_gate_front_matter` (`gates.py:60-75`) still only checks
  key-presence for `("title", "document")` (`gates.py:34`). No title-plausibility, date, or
  reply-to shape check. Not implemented.
- **MC2 TOC-leak:** `run_gates` (`gates.py:153-162`) returns exactly five gates
  (`non_empty`, `front_matter_valid`, `heading_monotone`, `no_empty_code`, `no_empty_table`).
  No `no_toc_leak` gate. Not implemented.
- **MC3 photocopy-golden warning:** `score.py` has no ideal-vs-source divergence detector.
  Not implemented.
- **MC4 sub-resolution diff:** no `ideal_diff_lines` field on `WhiskerResult` (`score.py:58-95`).
  Not implemented.
- **MC5 labeled calibration:** `constants.py` edges are still adopted-from-repo, not fitted
  (whisker `CLAUDE.md` "Calibration status" confirms provisional). `test_calibrate.py` exists
  but the operating points are not committed.

`REGION_SOFT_COUNT = 1` (`constants.py:47`), so a single misaligned region still raises a soft
flag; the persona's cross-reference that raising it `> 1` is an open suggestion is accurate.
**CONFIRMED.**

---

## Persona 22 — Whisker-Boundary-Guardian — CONFIRMED (with a transitive-availability nuance)

**Claim: PyMuPDF imported in `tapetum_llm/` but NOT declared in whisker; add to the
`tapetum-llm` optional extra.**

Direct imports found:

```31:31:packages/whisker/src/whisker/tapetum_llm/textlayer.py
import pymupdf
```

```21:21:packages/whisker/src/whisker/tapetum_llm/vision.py
import pymupdf
```

(plus `tests/test_pdf_judge.py:15`). The declaration side:

```8:32:packages/whisker/pyproject.toml
dependencies = [
    "apted>=1.0.3",
    ... (no pymupdf) ...
    "tomd",
]

[project.optional-dependencies]
tapetum-llm = [
    "openai",
    "pipeline",
    "pydantic-ai",
    "pydantic>=2.0",
    "python-dotenv>=1.0",
]
```

`pymupdf` appears in neither the core deps nor the `tapetum-llm` extra. Two modules under the
opt-in lane `import pymupdf` directly. **CONFIRMED**: whisker imports a dependency it does not
declare, and the `tapetum-llm` extra is the correct place to add it.

**Nuance (honest partial):** the lane does not currently crash, because `pymupdf` is pulled in
**transitively via `tomd`** — `tomd` is a whisker CORE dependency (`pyproject.toml:20`) and
pins `pymupdf~=1.27.0` (documented in `packages/whisker/research/persona/12-license-compliance.md:20`,
resolved to 1.27.2.3 in the lock). So the finding is a latent declaration-hygiene defect, not
a live import failure: if `tomd` ever dropped pymupdf, the `tapetum-llm` lane would break with
no declared dependency to catch it, and a `pip install whisker[tapetum-llm]` that somehow
resolved tomd without pymupdf would fail at import. The fix is one line in the extra; it does
not require touching any other package, so the boundary claim ("all fixes stay under
`packages/whisker/`") holds.

---

## Persona 24 — Test-Suite-Auditor — CONFIRMED

**Claim: `test_tables.py` does not exist; `parse_pipe_tables` / single-dash untested.**

Full listing of `packages/whisker/tests/*.py` (30 files) contains no `test_tables.py`.
`tables.py`'s public API (`parse_pipe_tables`, `parse_html_tables`, `split_pipe_cells`) has no
dedicated unit test. It is exercised only INDIRECTLY:

- `test_gates.py:69-96` tests the *gate copy* of the separator regex (`no_empty_table`),
  never `tables.py`.
- `test_facts.py` and `test_bench.py` feed pipe tables through `check_facts` / `table_score`,
  so `parse_pipe_tables` runs, but no test targets it directly and none uses a single-dash
  (GFM-valid) separator.

**CONFIRMED.** The gap matters precisely for persona 19's fix: the `-{2,}`→`-+` change lands
in a module with zero direct tests, and the one behavior it changes (single-dash separators)
is untested on both the `tables.py` and `gates.py` sides. The persona's "each MC fix needs a
PR-replay regression test" is the right guard; for the table fix specifically, a new
`test_tables.py` with a parametrized single-dash case is the minimum.

---

## Cross-finding synthesis

The single highest-leverage, lowest-risk item across these five personas is **persona 19's
`-{2,}`→`-+` fix, exported as one shared constant** (folding in persona 24's missing
`test_tables.py`): it is a genuine GFM-compliance bug, present in duplicate, that breaks no
existing test, and its only residual risk (prose false-positives) is bounded by the existing
pipe guard. Persona 22's pymupdf declaration is the second cheapest (one line, real hygiene
gap masked by a transitive pin). Personas 20 and 21 are diagnostic confirmations that the
current fold behavior and the MC1-MC5 gap are exactly as documented — no code currently
misbehaves; the work is additive.
