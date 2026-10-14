# Opus Meta-Review B: MC3 (Photocopy-Golden) + MC4 (Sub-Resolution) signals

**Reviewer:** Meta-Reviewer B, Golden-QA Gap Research Swarm
**Date:** 2026-07-15
**Assigned personas:** 15 (Photocopy-Golden-Detector), 16 (Sub-Resolution-Diff-Stratege), 01 (olmocr-bench), 03 (docling-eval), 09 (markitdown-firecrawl)
**Method:** Every claim re-verified against the actual whisker source and the cited repos (repos live at `packages/whisker/research/repos/`, gitignored, verified present on disk with `rg --no-ignore`).

---

## Verdict table

| Persona | Rating | One-line basis |
|---|---|---|
| 01 olmocr-bench | **PARTIALLY_CONFIRMED** | Repo facts exact-verified; but the "JSONL fact-check layer" is ALREADY built in whisker (`facts.py` Lane 3). Net-new value low. |
| 03 docling-eval | **CONFIRMED** | `nanquantile(q=0.1)` worst-10% and `verify_table_v2` verified; persona correctly says it does NOT close MC3/MC4. |
| 09 markitdown-firecrawl | **CONFIRMED** | `must_include` substring anchors + separate metadata axis verified; accurate, tangential to MC3/MC4 core. |
| 15 Photocopy-Golden-Detector | **PARTIALLY_CONFIRMED** (one sub-claim **REFUTED**) | Seam + `normalize_for_exact_lane` confirmed; core heuristic "tiny candidate-vs-ideal diff ⇒ uncurated photocopy" REFUTED (fires on good conversions). |
| 16 Sub-Resolution-Diff-Stratege | **CONFIRMED** | `clean_string` strips punctuation (line 115/126); dropped period invisible to all four metrics; `normalize_for_exact_lane` exists and a unified_diff line-count WOULD catch it. |

**Tally:** 3 fully CONFIRMED (03, 09, 16), 2 PARTIALLY_CONFIRMED (01, 15), 1 REFUTED sub-claim (persona 15's photocopy heuristic).

---

## Answers to the five required verification questions

### Q2. Does `metrics.clean_string` actually strip punctuation (MC4 claim)? At what line?

**CONFIRMED.** `packages/whisker/src/whisker/metrics.py`:

```115:126:packages/whisker/src/whisker/metrics.py
_CLEAN_KEEP_RE = re.compile(r"[^\w\u4e00-\u9fff]")


def clean_string(input_string: str) -> str:
    """OmniDocBench content normalizer: keep alnum + CJK, drop everything else."""
    input_string = replace_textcircle(input_string)
    input_string = (
        input_string.replace("\\t", "").replace("\\n", "")
        .replace("\t", "").replace("\n", "")
        .replace("/t", "").replace("/n", "")
    )
    return _CLEAN_KEEP_RE.sub("", input_string)
```

The regex at **line 115** matches every char that is NOT `\w` (alnum + underscore) or CJK; **line 126** deletes all of them. A period is neither `\w` nor CJK, so it is stripped.

**Precision correction to persona 16's wording (still CONFIRMED in conclusion):** `clean_string` is NOT literally the function inside `text_nid`. `text_nid` (metrics.py:343) normalizes with `_normalize_text` (whitespace-collapse only, line 84). `clean_string` reaches the metrics via the `normalized_text = clean_string(textblock2unicode(...))` wrapper applied at the CALL SITES:
- Ideal-panel nid: `golden_ideals.py:135` `text_nid(normalized_text(md), normalized_text(ideal))`.
- Oracle nid: `score.py:269` `text_nid(normalized_text(md_text), normalized_text(reference_md))`.
- Bench nid: `match.py:240,268` `block_metrics`/`block_text_nid` default `normalize=normalized_text` (verified).

So punctuation is stripped on ALL three nid paths. `content_recall` is period-blind independently: `content_tokens` splits on `_CONTENT_TOKEN_RE = \w+` (metrics.py:355), so punctuation never becomes a token regardless of `clean_string`. TEDS/MHS score table/heading structure, so a body-text period is irrelevant to them. **Net: a single dropped period is invisible to nid, teds, mhs, and content_recall — persona 16's conclusion holds.**

### Q3 (MC3). Is `score_against_ideal` (in `score.py`/`golden_ideals.py`) where the NID >= 0.99 warning would go? Write the EXACT 3-line check.

**CONFIRMED seam.** The ideal panel is computed in `score_against_ideal` (`golden_ideals.py:114`, returns `IdealPanel{nid, teds, mhs, recall, overall}`) and its axes are flagged in `_decide` (`score.py:205-215`, the `if ideal is not None:` block). A photocopy warning attaches at exactly these two points: compute the diff-line count in `score_against_ideal` (it already has both `md_text` and `ideal_md` in scope), surface the flag in `_decide`.

Exact 3-line check (drop into `_decide` after the existing ideal block, given `panel` and the candidate/ideal text carried onto `IdealPanel`; `PHOTOCOPY_NID_EDGE=0.99`, `PHOTOCOPY_DIFF_MAX_LINES=10` as named constants):

```python
diff_lines = len(list(difflib.unified_diff(
    normalize_for_exact_lane(ideal_md).splitlines(),
    normalize_for_exact_lane(md_text).splitlines(), lineterm="")))
if (panel.nid >= PHOTOCOPY_NID_EDGE and panel.recall >= PHOTOCOPY_NID_EDGE
        and (panel.mhs is None or panel.mhs >= PHOTOCOPY_NID_EDGE)
        and diff_lines <= PHOTOCOPY_DIFF_MAX_LINES):
    soft.append("ideal may be uncurated photocopy of converter output (advisory)")
```

The seam and the mechanics are sound and minimal. **But the heuristic itself is refuted — see the refutation below.**

### Q4 (MC4). Would a `unified_diff` line-count metric catch the PR #294 dropped period? Does `normalize_for_exact_lane` exist, and where?

**CONFIRMED, yes and yes.** `normalize_for_exact_lane` exists at `golden.py:79-90`:

```79:90:packages/whisker/src/whisker/golden.py
def normalize_for_exact_lane(text: str) -> str:
    """Deterministic near-exact normalizer applied to BOTH sides before diff.

    Policy (html2text / pymupdf4llm precedent): collapse ``\\r\\n`` and ``\\r``
    to ``\\n``, strip trailing whitespace per line, and enforce a single
    trailing newline at EOF. This absorbs platform line-ending and
    trailing-space noise (the brittle part of byte-exact goldens on Windows
    checkouts) while keeping every meaningful character change visible.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    body = "\n".join(line.rstrip() for line in text.split("\n")).rstrip("\n")
    return body + "\n" if body else ""
```

It normalizes ONLY line endings and trailing whitespace — it does **not** strip punctuation. A dropped period changes the content of a line, so `difflib.unified_diff` over the two normalized surfaces emits that line, and a line-count > 0 fires. This is exactly the sub-metric-resolution sensitivity MC4 needs.

Note this exact mechanism ALREADY exists as Lane 1 stability: `golden._evaluate` (golden.py:164-179) runs `normalize_for_exact_lane` on both sides and computes `difflib.unified_diff`, failing on ANY change — but only against a committed `<pid>.expected.md` snapshot, not against the golden ideal. Persona 16's proposal is to reuse the same normalizer + diff on the **candidate-vs-ideal** pair as an advisory `ideal_diff_lines` signal. ~3 LOC, no new module, no new dependency.

### Q5. olmocr "JSONL fact-check layer": over-engineering for whisker, or genuine improvement? (Minimalism Ladder)

**Verdict: rebuilding it would be over-engineering; the architecture is ALREADY adopted.** Persona 01's repo facts are exact-verified (`olmocr/olmocr/bench/tests.py`):
- `class TextPresenceTest` at line 129;
- `threshold = 1.0 - (self.max_diffs / len(reference_query))` at line 168 (persona's formula verbatim);
- `fuzz.partial_ratio(...)` at line 169;
- `max_diffs: int = 0` default at line 100 (so `max_diffs=0` ⇒ threshold 1.0 ⇒ exact, the single-char sensitivity persona 01 cites).

Minimalism Ladder applied:
- **Rung 4 (already-installed / already-built):** whisker's `facts.py` already implements this exact pattern. `_present_within` → `_best_match` uses `fuzz.partial_ratio_alignment` widened by a `max_diffs` budget (facts.py:299-326), `max_diffs` defaults to `0` (facts.py:111), facts are stored as `<pid>.facts.jsonl`, and `auto_baseline_checks` (facts.py:648) is explicitly documented as the "olmOCR-pattern". Lane 3 (comprehension) IS the olmocr source-anchored fact layer.
- Therefore building a NEW "JSONL fact-check layer" duplicates Lane 3 → **over-engineering**, violates "don't add what exists."
- **The genuine (non-code) improvement:** the olmocr contribution that ISN'T yet fully realized is *coverage and provenance*, not architecture — mine facts from SOURCE (facts.py already verifies needles at authoring) and expand from 5/381 papers (a known gap in whisker's CLAUDE.md). That is authoring work, not a new subsystem.

For MC4 specifically, olmocr's only net idea (`max_diffs=0` exactness) is already the whisker default. So olmocr adds nothing new to MC4 that isn't in the tree.

---

## The single most impactful adoption for MC3+MC4

**Persona 16's `ideal_diff_lines`: an advisory review signal equal to the count of `difflib.unified_diff` lines between `normalize_for_exact_lane(candidate)` and `normalize_for_exact_lane(ideal)`, fired when > 0, computed on the existing ideal-panel path.**

Why it wins:
- **Directly closes MC4.** It is the ONLY proposed signal that restores sensitivity BELOW the numerical resolution of nid/teds/mhs/recall. The PR #294 single dropped period rounds every aggregate metric to 1.0; the exact diff is the only thing that sees it.
- **Minimal by the ladder.** ~3 LOC. Reuses `normalize_for_exact_lane` (golden.py:79, already exists) and the ideal panel in `score_against_ideal`/`_decide` (already exists). No new module, no new dependency, stdlib `difflib` only. Stays entirely under `packages/whisker/src/whisker/` (boundary-clean).
- **Advisory, so it cannot destabilize the calibrated hard gate** (matches whisker's ideal-panel-is-advisory invariant).

Its documented blind spot IS the MC3 residual: when the ideal is itself a photocopy of buggy tomd output, candidate ≈ ideal, `ideal_diff_lines ≈ 0`, and the shared bug is invisible to the diff. Closing that requires an **ideal-vs-SOURCE** signal, which no assigned persona actually delivers (see refutation). That is the honest remaining gap, not something the diff-line signal can fix.

---

## Finding I refute (with evidence)

**REFUTED — Persona 15's core photocopy heuristic: "ideal-panel NID >= 0.99 AND MHS/recall >= 0.99 AND candidate-vs-ideal `unified_diff` <= ~10 lines ⇒ warn that the ideal may be an uncurated photocopy."**

The signal it uses (small candidate-vs-ideal distance) does not discriminate the failure it claims to detect:

1. **A tiny candidate-vs-ideal diff is the EXPECTED state of a GOOD conversion.** The candidate SHOULD be close to a correct ideal. A genuinely excellent tomd conversion scored against a genuinely correct human ideal also scores nid/mhs/recall ≥ 0.99 with a near-zero diff. So the trigger fires identically on (a) "ideal is an uncurated photocopy of buggy tomd" and (b) "tomd is correct and matches a correct ideal." The signal has zero discriminating power between the two — it flags the best papers. High false-positive rate → alarm fatigue → reviewers learn to ignore it, which is worse than no signal.

2. **MC3's actual root cause is ideal-vs-SOURCE divergence** (baseline 00, MC3: "No signal measures how much the golden diverges from the SOURCE"). Persona 15 measures ideal-vs-CANDIDATE. Its own fallback ("Optional reconcile: diff ideal vs fresh `tomd_markdown(source)`") is STILL ideal-vs-tomd-output, not ideal-vs-source, so it inherits the same shared-bug blindness. Neither variant touches the source, so neither can detect a photocopy in principle.

3. **The right layer already exists and is the prevention, not a score-time heuristic.** Verified: tomd blocks byte-identical seeds at bless time via `is_unedited_seed` (`packages/tomd/src/tomd/lib/golden_qa.py:271`, gated at line 618). That is the correct place to prevent photocopy ideals (at authoring). A score-time "may be photocopy" advisory that fires on good papers is not a substitute and adds noise.

What CONFIRMS (the non-refuted part of persona 15): the *seam* is real (`score_against_ideal` + `_decide`), `normalize_for_exact_lane` is available, and the cross-package `is_unedited_seed` claim is accurate. The mechanics are fine; the inference is not. Hence PARTIALLY_CONFIRMED overall with the heuristic REFUTED.

**What would flip the refutation:** evidence that curated ideals in the corpus produce a *materially larger* candidate-vs-ideal diff than uncurated ones (i.e. the distributions separate). Absent that separation, the signal is noise. The only robust MC3 detector remains an ideal-vs-source metric, which is out of scope for a minimal fix and needs its own calibration.

---

## Notes on personas 03 and 09 (CONFIRMED, tangential to MC3/MC4)

- **03 docling:** `nanquantile(q=0.1)` "worst 10% of pages" verified at `standard_pdf_pipeline.py:1076` and `legacy_standard_pdf_pipeline.py:259`; `verify_table_v2` at `tests/verify_utils.py:134`. Persona is accurate INCLUDING its own admission that docling "freezes converter output like our bench" and has "no source-anchored metadata/TOC validation" — i.e. it does not help MC3/MC4. Worst-tail aggregation is a bench-corpus idea, orthogonal to single-paper sub-resolution.
- **09 markitdown/firecrawl:** `must_include` substring anchors verified at `markitdown/.../tests/_test_vectors.py`. Its real recommendation ("separate metadata axis, not more `ref_nid` slack") targets MC1, not MC3/MC4. whisker already keeps metadata-shaped checks separable (gates + facts). Accurate but not an MC3/MC4 lever.
