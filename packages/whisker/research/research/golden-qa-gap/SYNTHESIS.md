# Golden-QA Gap Research — Synthesis

**Date:** 2026-07-15
**Swarm:** 3 web foragers + 25 Composer-2.5 personas + 5 Opus 4.8 meta-reviewers
**Target:** `packages/whisker/` (deterministic gates, bench, LLM lane)
**Scope:** Close the 5 miss-classes (MC1-MC5) verified during PRs #282-295

## Executive Summary

The swarm confirmed all five miss-classes are still open in the live source (Meta-Reviewer D, persona 21: `run_gates` returns exactly five gates, no `no_toc_leak`, no front-matter-truth check, no diff-line signal), and that every viable fix stays under `packages/whisker/src/whisker/` (Meta-Reviewer D, persona 22). Two things are ready to ship now: a narrow **TOC-leak hard gate** (MC2) that is runtime-proven to fail PR #290 and #293 (Meta-Reviewer A, persona 14), and the **`-{2,}`→`-+` table-separator fix** that corrects a real GFM bug duplicated in two files and breaks no test (Meta-Reviewer D, persona 19). One tier down, behind test fixtures, sit a **soft** front-matter-truth check (MC1) and stripping front-matter *truth* out of the LLM's scope (MC5a). The honest bad news: the cheap versions of **MC3 (photocopy-golden)** and **MC4 (sub-resolution)** do **not** work, both Meta-Reviewers B and E found the naive signals fire identically on healthy and broken papers, so they are deferred, not closed. LLM recalibration (Platt/VERDI) is un-buildable today because no labeled corpus exists (Meta-Reviewer C, persona 17.5; Meta-Reviewer E).

## Verified Adoption Path

### Tier 1: Ship Immediately (verified, <15 LOC, no new deps, low risk)

#### T1.1 — MC2 TOC-leak hard gate

- **File:** `packages/whisker/src/whisker/gates.py` — new `_gate_no_toc_leak(body)`, wired into `run_gates` (`gates.py:153-162`).
- **LOC:** ~12 (Meta-Reviewer E; reuses the existing fence-aware `_iter_body_lines` at `gates.py:78`, so no new module).
- **Gate type:** HARD, restricted to two zero-ambiguity TOC fingerprints (Meta-Reviewer E, persona 14).
- **What it catches:** a body line that is a bare `table of contents` / `contents` label, or a heading whose page-digit-stripped normalized text duplicates an earlier heading where one occurrence carried a trailing `\s+\d{1,4}$` page number.
- **What PR would have failed:** PR #290 (p1122r3, duplicate `## 1. Introduction` with page digits) and PR #293 (p0533r9, `## Contents` label). Both runtime-proven to hard-fail; a clean paper with legitimate duplicate `## Example` headings passes (Meta-Reviewer A, persona 14).
- **Risk (Steelman, persona 25 via Meta-Reviewer E):** LOW for the narrow signatures. Requirement: filter to `kind == "text"` so a `## Contents` inside a code fence never trips it.
- **Actionable code (runtime-verified, Meta-Reviewer A):**

```python
_TRAILING_PAGENUM_RE = re.compile(r"\s+\d{1,4}\s*$")
_SECTION_PREFIX_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
_TOC_LABEL_RE = re.compile(
    r"^(?:#{1,6}\s+)?(?:table\s+of\s+contents|contents)\s*$", re.IGNORECASE
)


def _normalize_heading_text(text: str) -> str:
    text = _TRAILING_PAGENUM_RE.sub("", text.strip())
    text = _SECTION_PREFIX_RE.sub("", text)
    return " ".join(text.split()).casefold()


def _gate_no_toc_leak(body: str) -> GateResult:
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
            return GateResult("no_toc_leak", False,
                f"duplicate heading {raw!r}; a table of contents likely leaked into the body")
        seen[key] = seen.get(key, False) or had_pagenum
    return GateResult("no_toc_leak", True)
```

The `(seen[key] or had_pagenum)` guard is load-bearing: two legitimately identical headings that never carried a page number do not trip the gate (Meta-Reviewer A, persona 14).

#### T1.2 — Table-separator GFM fix (MC-adjacent)

- **Files:** `packages/whisker/src/whisker/tables.py:36` and `packages/whisker/src/whisker/gates.py:132`.
- **LOC:** ~4 net.
- **Gate type:** fixes the existing `no_empty_table` hard gate.
- **What it catches:** `| - | - |` (single hyphen per column) is a valid GFM §4.10 delimiter row that both scanners currently miss because both require `-{2,}` (Meta-Reviewer D, persona 19). The two regexes are **byte-for-byte identical and duplicated** (`_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")` at both `tables.py:36` and `gates.py:132`), a latent DRY drift bug.
- **Fix:** change `-{2,}` to `-+` and export ONE shared constant from `tables.py`, imported by `gates.py`. `-+` is a strict superset of `-{2,}`, so every committed test separator still matches (`test_gates.py:72,78,93`, `test_facts.py:26`, `test_bench.py:20` all use ≥2 dashes); nothing regresses (Meta-Reviewer D, persona 19+24).
- **What PR would have failed:** none in the #282-295 set; this is the single highest-confidence lowest-LOC correctness win the swarm found (Meta-Reviewer E, persona 10/19).
- **Risk (Steelman, persona 25):** LOW. `-+` makes a lone `-` cell in pipe-adjacent prose marginally easier to misread as a table, bounded by the existing `"|" not in line` guard (`gates.py:142`, `tables.py:71`) which the regex change does not touch (Meta-Reviewer D).
- **Test needed:** a new `test_tables.py` with a parametrized single-dash case, because `parse_pipe_tables` currently has zero direct tests (Meta-Reviewer D, persona 24).

#### T1.3 — Declare `pymupdf` in the `tapetum-llm` extra (hygiene, adjacent)

- **File:** `packages/whisker/pyproject.toml`, `[project.optional-dependencies].tapetum-llm`.
- **LOC:** 1 line.
- **What it fixes:** `textlayer.py:31` and `vision.py:21` both `import pymupdf`, but `pymupdf` appears in neither the core deps nor the `tapetum-llm` extra (verified against `pyproject.toml:8-32`). It only resolves today transitively via the core `tomd` dependency's `pymupdf~=1.27.0` pin (Meta-Reviewer D, persona 22; Meta-Reviewer A, persona 18). A latent declaration defect, not a live crash. Boundary-clean: one line, no other package touched.

### Tier 2: Ship After Testing (15-30 LOC, needs test fixtures)

#### T2.1 — MC1 Front-Matter Truth (title≠first-H2 + reply-to shape)

- **File:** `packages/whisker/src/whisker/gates.py` — `_gate_front_matter` gains a `body` parameter (signature change: it is currently `_gate_front_matter(fm_lines)` at `gates.py:60`, called with only `fm_lines` at `gates.py:158`), plus the `run_gates` call site.
- **LOC:** ~18-22 (Meta-Reviewer E corrected the skeptic's "12": the signature/plumbing change is real LOC the byte count omitted).
- **Gate type:** **SOFT (review), NOT hard.** Meta-Reviewer E explicitly overrides persona 23 (which said hard): Steelman (persona 25) documents the exact false-flag (a paper whose title genuinely equals its opening section, normalization strips the section number so `title: "Introduction"` + `## Introduction` would false-fail per Meta-Reviewer A). With no labeled corpus, whisker's own doctrine is "review beats a false pass."
- **What it catches:** front-matter `title` equal (after page-digit/section-prefix normalization) to the first body heading, or `reply-to` with >5 entries (a body list captured as authors).
- **What PR would have failed:** PR #290 (p1122r3), `title="1. Introduction"` normalizes to `introduction` = first heading `## 1. Introduction 3`; the 18-entry `reply-to` is a second independent trip. Both runtime-proven (Meta-Reviewer A, persona 13).
- **Risk (Steelman, persona 25):** MED. False-flag on title==first-section papers; mitigation is soft-gating + firing only on the TOC-leak fingerprint (section prefix or stripped page digit present). Reply-to shape (`len > 5`) is near-zero false-positive.
- **Test needed:** PR-replay fixture for p1122r3, currently pinned `front_matter_valid: true` in `test_gates.py` (Meta-Reviewer D, persona 24).

#### T2.2 — MC5(a): remove front-matter TRUTH from the LLM's scope

- **Files:** `packages/whisker/src/whisker/tapetum_llm/adjudicate.py`, `tapetum_llm/pdf_judge.py`.
- **LOC:** ~6, plus the empty-evidence-drop demote which is **already built** (`_custom_decide` at `adjudicate.py:300-305` demotes a pass whose evidence was emitted-then-all-dropped; Meta-Reviewer C, persona 17.1).
- **Gate type:** advisory (tapetum never gates).
- **What it does:** the LLM only ever sees the markdown, so it structurally cannot verify the title VALUE or a missing `date` against the source; #290 was the LLM asserting "front-matter correctly captures the title block" for an objectively wrong title (Meta-Reviewer C, persona 17.3). The deterministic MC1 gate (T2.1) takes over the truth role.
- **MANDATORY carve-out (Meta-Reviewer C):** do NOT strip the whole YAML block. `tapetum_llm.md:129` deliberately keeps front matter in scope so the LLM judges **key order** and a **corrupted `document` revision id**, defect classes it CAN see in the markdown alone. Blanket removal regresses that. Remove only the LLM's authority over front-matter *truth*; keep it judging front-matter *structure*.
- **Risk (Steelman, persona 25 via Meta-Reviewer E):** MED. Do NOT narrow `llm_clear_soft_review` (`fusion.py:187-202`), it is a live queue-shrink mechanism (see "What Still Works").
- **Test needed:** an adjudicate PR-replay fixture (Meta-Reviewer E, persona 24).

### Tier 3: Defer (>30 LOC, new deps, or genuinely open research)

#### T3.1 — MC3 real fix (ideal-vs-SOURCE reconcile)

- **Why deferred:** MC3's root cause is ideal-vs-SOURCE divergence (`bench.py:170-211` compares candidate vs reference, never vs source). The only honest detector is an ideal-vs-source / independent-second-conversion reconcile: a new pipeline that partially duplicates tomd (Meta-Reviewer B, Meta-Reviewer E). The cheap panel warning is REFUTED (see Refuted Proposals). tomd already prevents the worst case at authoring via `is_unedited_seed` (blocks byte-identical seeds at bless time), which is the correct layer, not a score-time heuristic (Meta-Reviewer B, persona 15).

#### T3.2 — MC4 robust fix (independent second-conversion byte-diff)

- **Why deferred:** the naive candidate-vs-ideal `ideal_diff_lines > 0 → review` (persona 16) floods the review queue, a curated ideal is *deliberately* edited away from raw tomd output, so `diff > 0` is the normal state for every curated-ideal paper (Meta-Reviewer E). The narrow "panel ~1.0 AND small nonzero diff" form is coupled to MC3: on a photocopy ideal the dropped character sits in BOTH sides → `diff == 0` → miss (persona 16's own caveat, confirmed Meta-Reviewer B). The robust fix is an independent second-conversion byte-diff (olmOCR source-anchored unit-test pattern) = new infra. Note the mechanic itself is sound: `normalize_for_exact_lane` exists at `golden.py:79-90` and does NOT strip punctuation, so a diff over it WOULD see PR #294's dropped period (Meta-Reviewer B) — the blocker is queue-flood and photocopy-coupling, not feasibility.

#### T3.3 — MC5(c) deterministic source↔markdown heading-outline diff

- **Why deferred:** ~30+ LOC, HTML-only. Both building blocks exist (`html_outline.extract_heading_outline` + `metrics._parse_headings` at `metrics.py:583`), and this is the single most impactful MC5 move because it converts a provably-unreliable LLM judgment (#282 false-clear, #295 false-positive, both WITH outline injection at `adjudicate.py:395-406`) into a pure-Python diff (Meta-Reviewer C, persona 17.4). Deferred because there is no reliable PDF outline: WG21 flat font ladders mis-level the font-size fallback, so it is HTML-only and PDF-unsolved (Meta-Reviewer A, persona 18). It MUST diff against the source outline, not an abstract "levels must be flat" rule, or it re-creates #295's false-positive deterministically (Meta-Reviewer C, false-fail hypothesis).

#### T3.4 — Platt / VERDI / bias-adjusted LLM calibration

- **Why deferred:** un-buildable today, not merely heavy. Every calibration method in the web cards (VERDI Platt-scaling, bias-adjusted estimator, linear probes) needs a labeled gold set first; whisker has none (`constants.py` edges stamped PROVISIONAL, must be refit on a labeled review set) (Meta-Reviewer C, persona 17.5; Meta-Reviewer E, persona 23).

#### T3.5 — MC1 date-presence sub-check

- **Why deferred:** needs `content.missing_regions` threaded from `score.py` into the gate; `gates.py` sees only the markdown and cannot know whether the *source* had a `Date:` label (Meta-Reviewer A, persona 13, check 3). Separate coupling from the pure-markdown MC1 checks in T2.1.

## Per Miss-Class Verdict

### MC1: Front-Matter Truth
- **Status:** PARTIALLY_CLOSEABLE
- **Adoption:** title≠first-H2 + reply-to-shape as a SOFT gate in `_gate_front_matter` (add `body` param). Date sub-check deferred (T3.5). (Tier 2, T2.1)
- **Evidence:** Meta-Reviewer A confirmed `_gate_front_matter` at `gates.py:60-75` only checks key-presence for `("title", "document")` (`gates.py:34,70`) and runtime-proved the title check hard-fails #290; Meta-Reviewer D (persona 21) confirmed not implemented.
- **Risk:** Steelman (persona 25): false-flag on a paper whose title genuinely equals its opening section. Meta-Reviewer E ⇒ soft, not hard.
- **Test needed:** p1122r3 PR-replay fixture (currently pinned `front_matter_valid: true`) (Meta-Reviewer D, persona 24).

### MC2: TOC Leak Detection
- **Status:** CLOSEABLE
- **Adoption:** new HARD `_gate_no_toc_leak(body)` in `gates.py`, narrow signatures only (TOC label + page-numbered duplicate heading). (Tier 1, T1.1)
- **Evidence:** Meta-Reviewer A runtime-proved it hard-fails #290 (duplicate heading) and #293 (`## Contents` label) while a clean legit-duplicate paper passes; Meta-Reviewer D (persona 21) confirmed `run_gates` (`gates.py:153-162`) returns only five gates, no `no_toc_leak`.
- **Risk:** Steelman/Meta-Reviewer E: LOW, provided the `kind == "text"` fence guard is honored.
- **Test needed:** p1122r3 + p0533r9 PR-replay fixtures (Meta-Reviewer D, persona 24).

### MC3: Photocopy-Golden Blindness
- **Status:** OPEN (deferred; cheap version does not work)
- **Adoption:** none in Tier 1/2. The honest fix (ideal-vs-source reconcile) is Tier 3 (T3.1).
- **Evidence:** Meta-Reviewer B REFUTED the panel-threshold heuristic (persona 15) — a small candidate-vs-ideal diff is the EXPECTED state of a GOOD conversion, so it fires identically on a photocopy ideal and on an excellent conversion; zero discriminating power. MC3's root cause (`bench.py:170-211` never compares against source) is unchanged.
- **Risk:** Steelman/Meta-Reviewer E: HIGH if wired as a soft flag (demotes perfect conversions → alarm fatigue). Value only as a non-verdict annotation, and whisker has no info-only channel today.
- **Test needed:** would require evidence that curated ideals produce a materially larger candidate-vs-ideal diff than uncurated ones (the distributions must separate); absent that, the signal is noise (Meta-Reviewer B, "what would flip the refutation").

### MC4: Sub-Resolution Defects
- **Status:** OPEN (deferred; cheap version does not work)
- **Adoption:** none in Tier 1/2. Robust fix = independent second-conversion byte-diff, Tier 3 (T3.2).
- **Evidence:** Meta-Reviewer B confirmed `clean_string` strips punctuation (`metrics.py:115-126`) and `content_recall` tokenizes on `\w+` (`metrics.py:355`), so a dropped period is invisible to nid/teds/mhs/recall (PR #294); and confirmed `normalize_for_exact_lane` (`golden.py:79-90`) does NOT strip punctuation so a diff-line count WOULD see it. Meta-Reviewer E deferred the naive form because curated ideals deliberately diverge from tomd (mass false-fail) and the narrow form inherits MC3's photocopy blindness.
- **Risk:** Steelman/Meta-Reviewer E: HIGH (naive form floods the review queue).
- **Test needed:** a run of `find_ideals_dir()` against live fixtures to learn how many papers carry an ideal (governs whether review volume is a flood or a trickle) (Meta-Reviewer E, open question).

### MC5: LLM Calibration
- **Status:** PARTIALLY_CLOSEABLE
- **Adoption:** MC5(a) remove front-matter *truth* from LLM scope + rely on the existing empty-evidence-drop demote (Tier 2, T2.2). MC5(c) deterministic heading-outline diff deferred (T3.3). Platt/VERDI recalibration deferred (T3.4).
- **Evidence:** Meta-Reviewer C confirmed 4/5 of persona 17: empty-evidence passes are NOT demoted (`adjudicate.py:300-305` requires truthy `evidence_spans`); `SIGNAL_AXIS_CONFLICT` fires only on pass∧fail axis sets (`adjudicate.py:236-238`), so a uniformly-wrong pass has no internal conflict; outline injection is live (`adjudicate.py:395-406`) yet demonstrably failed on #282/#295; bias-adjusted calibration needs a labeled holdout that does not exist.
- **Risk:** Steelman (persona 25): do NOT narrow `llm_clear_soft_review` (`fusion.py:187-202`), it is a live queue-shrink mechanism. MC5(a) is limited to the front-matter-truth scope, which is safe.
- **Test needed:** an adjudicate PR-replay fixture; and a labeled holdout corpus before ANY recalibration (Meta-Reviewer C, persona 17.5).

## Refuted Proposals

1. **Persona 15 — photocopy heuristic** ("ideal-panel NID ≥ 0.99 AND MHS/recall ≥ 0.99 AND candidate-vs-ideal diff ≤ ~10 lines ⇒ warn photocopy"). **REFUTED by Meta-Reviewer B:** a tiny candidate-vs-ideal diff is the expected state of a *good* conversion, so the trigger fires identically on a photocopy ideal and on an excellent conversion — zero discriminating power, high false-positive rate. The real root cause is ideal-vs-SOURCE divergence, which the heuristic never measures; even its fallback ("diff ideal vs fresh `tomd_markdown(source)`") is still ideal-vs-tomd-output, inheriting the same shared-bug blindness. Prevention already lives at authoring (`is_unedited_seed` in tomd).

2. **Persona 14 — page-number-heading regex** (`^#{1,6}\s+\d+(?:\.\d+)*\s+\S.+\s+\d{1,4}\s*$`). **REFUTED as written by Meta-Reviewer A:** it returns `False` on the exact #290 string `## 1. Introduction 3` (after `\d+` matches `1`, the pattern demands `\s+` but the next char is the literal `.`). Fix is `\.?` before `\s+`, but the check is not needed — the duplicate-heading check (T1.1) already catches #290.

3. **Persona 25 (Steelman) — "72 review→pass clears in sighting run".** **REFUTED by Meta-Reviewer C:** the string exists nowhere except `10-persona-findings.md:145` — not in any sidecar, report, or prior synthesis. The traceable figure is the **44% queue-shrink** the `llm_clear_soft_review` rule was designed to produce (`tapetum-golden-review-findings-2026-07-14.md:35-37`), with reproduced counts of "3/74 pass→review" over 197 sidecars. The mechanism is real; the number is fabricated/mis-transcribed. (See caveat under "What Still Works": the *mechanism* is confirmed.)

4. **Persona 23 (Simplicity-Skeptic) — MC1 as a HARD gate, and "MC3/MC4 done at 3-5 LOC".** **OVERRIDDEN by Meta-Reviewer E:** LOC is the wrong ranking axis — MC3 and MC4's cheapest-to-type checks are the least discriminating (they produce the same output on healthy and broken inputs = noise with a threshold). MC1 must be SOFT (Steelman false-flag + no calibration corpus). MC3/MC4 are deferred, not closed.

5. **"Remove front-matter from the LLM scope" (task paraphrase / persona 17 broad reading).** **REFUTED wholesale by Meta-Reviewer C:** blanket YAML removal would blind the LLM to key-order and corrupted-`document`-id defects it legitimately judges (`tapetum_llm.md:129`). Only front-matter *truth* is removed; front-matter *structure* stays in scope.

6. **olmocr "new JSONL fact-check layer" (persona 01).** **REFUTED as over-engineering by Meta-Reviewer B:** the architecture is ALREADY built as whisker's Lane 3 (`facts.py`, `_present_within`/`_best_match` with a `max_diffs` budget defaulting to 0, `auto_baseline_checks` documented "olmOCR-pattern"). The genuine gap is coverage/provenance (5/381 papers), which is authoring work, not a new subsystem.

7. **Naive MC4 `ideal_diff_lines > 0 → review` (persona 16).** **REFUTED as a soft signal by Meta-Reviewer E:** floods the review queue because curated ideals are deliberately edited away from raw tomd output. Sound mechanic, wrong wiring.

## What Still Works (Steelman)

Meta-Reviewer C re-verified persona 25's steelman against code; every "what works" claim traces except the "72" number (refuted above). Keep these — a fix must not regress them:

- **Three-lane agreement + low uncertainty** cleared PR #286 (`00-baseline.md:66`, documented runtime).
- **The LLM independently caught 31 dropped `constexpr` at conf 0.95** in PR #293 — a genuine hit the deterministic lane missed (`00-baseline.md:66`).
- **`clear_blocked_missing_region`** prevents an unsafe LLM upgrade when the deterministic lane detected missing source regions (`fusion.py:171-184`), demonstrated on P0957R8.
- **Ungrounded evidence quotes are dropped** (`grounding.py:238-239` + `adjudicate.py:294-295`), and an emitted-then-fully-dropped pass demotes to review (`adjudicate.py:300-305`).
- **`screen_pages`** (deterministic per-page recall screen, `pdf_judge.py:279-304`) closed p0957r8 end-to-end.
- **Rubric-bleed is annotated** (`pdf_judge.py:111-126`), and **sanctioned tomd uncertainty markers** are not flagged as defects.
- **`llm_clear_soft_review`** (`fusion.py:187-202`) is a live, intentional queue-shrink (the real, traceable figure is a **44% queue-shrink**, not "72 clears"; Meta-Reviewer C). Do not narrow it.
- **The narrow benign-region fold is by design, not a bug:** `_is_benign_region_only` (`score.py:234-238`) requires every soft flag to contain `"misaligned region"`, so an advisory `ref_nid` flag correctly keeps a paper at `review` (Meta-Reviewer D, persona 20). Never fold ideal-panel flags (ideals are ground truth).

## Open Questions

1. **How many papers carry a golden ideal?** Governs whether MC1/MC4 review volume is a flood or a trickle. Meta-Reviewer E could not run `find_ideals_dir()` against the live fixtures.
2. **MC3 and MC4 have no cheap detector.** Both genuinely need an ideal-vs-SOURCE or independent-second-conversion reconcile (new infra). Until one exists, both remain open, not closed.
3. **No PDF heading-outline oracle is reliable.** WG21 flat font ladders mis-level the `IdentifyHeaders` font-size fallback; `doc.get_toc()` works only when the PDF ships a bookmark outline (Meta-Reviewer A, persona 18). MC5(c) stays HTML-only.
4. **No labeled calibration corpus exists.** Every LLM-judge recalibration method is blocked on it (Meta-Reviewer C, persona 17.5).
5. **Does any real WG21 paper have a title that legitimately equals its opening section heading?** This is the one documented MC1 false-fail risk (Steelman, persona 25); it determines whether the soft title check ever needs demotion further.

## Appendix: Research Artifacts

Produced by this swarm under `research/golden-qa-gap/`:

- `00-baseline.md` — evidence baseline: the 5 miss-classes with file:line anchors, repo comparison table, 25-persona roster.
- `05-web.md` — web finding cards (Q1 golden-fixture validation, Q2 sub-resolution detection, Q3 LLM-judge calibration).
- `10-persona-findings.md` — 25 consolidated persona summaries (12 repo analysts, 8 miss-class hunters, 5 process personas).
- `opus-A-mc1-mc2-gates.md` — Meta-Reviewer A: MC1+MC2 gate verification (personas 13, 14, 06, 07, 18); runtime-verified gate code.
- `opus-B-mc3-mc4-signals.md` — Meta-Reviewer B: MC3+MC4 signals (personas 15, 16, 01, 03, 09); photocopy heuristic refutation.
- `opus-C-mc5-llm.md` — Meta-Reviewer C: MC5/LLM lane (personas 17, 25, 02, 05, 12); "72" refutation, front-matter carve-out.
- `opus-D-boundary-tests.md` — Meta-Reviewer D: boundary/tables/tests/fold (personas 19, 20, 21, 22, 24); table-sep + pymupdf confirmations.
- `opus-E-adoption-path.md` — Meta-Reviewer E: adoption path (personas 23, 04, 08, 10, 11); LOC corrections, tier assignment, gate-hardness overrides.
- `SYNTHESIS.md` — this document.
