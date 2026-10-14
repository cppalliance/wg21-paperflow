# OPUS META-REVIEWER A - Metric Validity & Calibration

Independent re-verification (Opus, 2026-06-25). Every row below was checked
against source (file:line) and/or runtime, NOT taken from the persona reports.
Runtime probes were run read-only (`uv run --package whisker python -`, single
`whisker P3941R2 --no-reference --no-write`). No production file was modified.

Domain scope: the *measurement layer* and *calibration* (personas 01, 02, 05,
06, 10, 20). I did not re-audit guard/facts orchestration except where a metric
claim depends on it.

## Claim verification

| # | Persona claim (sev) | Verdict | Evidence I checked |
|---|---|---|---|
| 01-M1 | Review tier = expected stripping noise; `REGION_SOFT_COUNT=1`, 186/382 (HIGH) | **CONFIRMED** | `constants.py:47`, `score.py:164-166`; runtime `_decide(1.0,0,1,0,100,0,clean,None)` → `('review',[],['1 misaligned region(s)'])`. 186/205 count from baseline §3a (not re-run). |
| 01-M2 | Hard-gate thresholds borrowed, zero measured OC (HIGH) | **CONFIRMED** | `constants.py:11-15` "PROVISIONAL … not yet fitted"; no `--labels` file exists in repo (§5). |
| 01-M3 | `unigram_coverage` = multiset recall, blind to order/semantic swaps (HIGH) | **CONFIRMED** | `score.py:156-160` gate is `< FAIL_EDGE` only; runtime `_decide(1.0, clean)` → `pass`; `content_tokens` is a bag (`metrics.py:358-369`). Construct, not the cited `check_content.py:621-624` (a tomd line I did not verify). |
| 01-M4 | `heading_monotone` fails typography not content; ~64% of fails (HIGH) | **CONFIRMED** | `gates.py:96-112`; runtime `whisker P3941R2 --no-reference` → `fail … uni=0.999 cov=0.997 drift=0.002 qa=95 gate:heading_monotone:H2 -> H4` (exit 5). 9/14 from §3a. |
| 01-M5 | `ref_overall=(nid+teds+mhs)/3` construct-invalid; diverges from bench null-eligibility (HIGH) | **CONFIRMED** | `score.py:213-216` always `/3` with `table_score` returning 1.0 when no tables (`bench.py:154-155`) and `mhs` returning 1.0 when no headings (`metrics.py:690-691`), vs `bench.py:223-228, 238-243` nulling teds/mhs. Runtime: nid=0.6,teds=mhs=1.0 → ovr=0.867. |
| 01-M6 | `REF_NID_ADVISORY_EDGE=0.85` below corpus mean 0.836; 147/382 (MED) | **PARTIALLY-CONFIRMED** | Edge + advisory-only path confirmed (`constants.py:87`, `score.py:175-178`). Corpus mean 0.836 / 147 are baseline §3b numbers I did not re-run (oracle run is slow); mechanism is sound. |
| 01-M7 | Bench `overall` unweighted mean, excludes `content_recall` (MED) | **CONFIRMED** | `bench.py:238-243` mean of eligible {nid,teds,mhs}; `content_recall` separate (`bench.py:229-233`, `285-291`). |
| 01-M8 | `normalized_text` erases punctuation/markup (LOW) | **CONFIRMED** | `metrics.py:115-126` keeps only `\w`+CJK. |
| 02-C1 | No threshold ever validated; TPR/FPR/precision unknown (CRITICAL) | **CONFIRMED** | `constants.py:11-15`; no labels artifact; §5. |
| 02-C2 | Hard-fail dominated by structural gates, not the unigram floor `calibrate` targets (HIGH) | **CONFIRMED** | `__main__.py:829-838` fits only coverage edges; `gates.py` failures are independent; 9/14 heading vs 3/14 unigram (§3a). |
| 02-C3 | Review tier driven by signals `calibrate` does not model (regions) (HIGH) | **CONFIRMED** | `calibrate` consumes only `(coverage,label)` (`__main__.py:789-791, 829-830`); regions/drift/qa/uncertain/ref_nid all in `_decide` (`score.py:164-178`) and untouched by the fit. |
| 02-C4 | `calibrate` label defs misalign with production verdict fusion (HIGH) | **CONFIRMED** | `review_samples` positive = label∈{fail,review} but value = coverage only (`__main__.py:830`); live `_decide` stacks 6 independent signals. A fitted edge reports OC for ONE sub-rule, not `verdict==review`. |
| 02-C5 | ROC fitter correct; Youden fallback can silently violate FPR ceiling on infeasible data (MED) | **REFUTED (on the Youden mechanism); fitter-correct part CONFIRMED** | Fitter is correct (`calibrate.py:150-195`; `test_calibrate.py`). BUT the min candidate threshold flags nothing → `fp=0,fpr=0` (`calibrate.py:124-147`), so the feasible set is **never empty** and the `else: Youden` branch (`calibrate.py:188-190`) is **unreachable dead code**. Runtime: bad>good and fully-interleaved sets at `target_fpr=0.05` *and* `0.00` all return `method=max_tpr_at_fpr`, degenerate `thr=min, tpr=0`. See "Persona errors". |
| 02-C6 | Single global edge weak; bimodal html/pdf; low fail sensitivity (MED) | **CONFIRMED** | One edge pair for all papers (`constants.py:37-38`); fail fires on ~0.8% (3/382 §3a/b). Stratification absent. |
| 02-C7 | Advisory `REF_NID_EDGE` floods review with oracle on (MED) | **PARTIALLY-CONFIRMED** | Mechanism confirmed (`score.py:175-178`); 147/382 from baseline §3b, not re-run. |
| 02-C8 | FPR budget disagreement: CLAUDE.md 10% vs `DEFAULT_TARGET_FPR=0.05` (LOW) | **CONFIRMED** | `calibrate.py:41-44` = 0.05; whisker `CLAUDE.md` "Calibration status" says "FPR <= 10%". Audit-trail inconsistency, not a code bug. |
| 05-T1 | Core `_TEDS.evaluate` matches PubTabNet/OmniDocBench algorithm (HIGH) | **CONFIRMED (by code)** | `metrics.py:445-516`: lxml DOM, `xpath('.//*')` denominator, td-only tokenize, `rename`→1.0 on tag/colspan/rowspan diff (`431-442`). I verified structure, not a fresh upstream import (persona did the side-by-side). |
| 05-T2 | `_normalize_table_html` mandatory: th→td, thead/tbody strip, wrap (HIGH) | **CONFIRMED** | `metrics.py:519-537`. |
| 05-T3 | Bench NOT leaderboard-equivalent: index-paired mean, not first-table-only (HIGH) | **CONFIRMED** | `bench.py:150-163`: `for k in range(max(len))`, pad with `<table></table>`, `total/pairs` (mean). OmniDocBench scores `body/table[0]`. |
| 05-T4 | Cell rename = raw char tokens, no whitespace/unescape (matches OmniDocBench, not opendataloader fork) (MED) | **CONFIRMED (by code); exact 0.8 not re-run** | `metrics.py:428-429, 439-442` calls `normalized_distance` on raw token lists. The 0.8-vs-1.0 fork delta is persona runtime I did not reproduce. |
| 05-T5 | rapidfuzz swap, parity frozen for str/int not TEDS char-lists (MED) | **CONFIRMED** | `metrics.py:429` rapidfuzz; `test_edit_distance_parity.py` scope = strings+int tuples. |
| 05-T6 | Tests pin one PubTabNet case; no upstream fixture import (MED) | **CONFIRMED** | Lane 2 corpus empty (§4); single golden vector per baseline. |
| 05-T7 | Zero-denominator guard returns 1.0 (deviation) (LOW) | **CONFIRMED** | `metrics.py:506-510`. |
| 05-T8 | `structure_only` (TEDS-S) exposed but not wired (LOW) | **CONFIRMED** | `metrics.py:540-551`; `bench.py:162` calls full `teds`. |
| 06-E1 | All-punctuation/symbol strings → NID=1.0 on oracle path (HIGH) | **CONFIRMED** | Runtime `text_nid(normalized_text('!!!'),normalized_text('???'))=1.0`; `'# ## | * * *'` vs `'--- === ...'` = 1.0. `normalized_edit_distance('','')=0.0` (`metrics.py:75-76`). |
| 06-E2 | `normalized_text` does not strip YAML front matter (MED) | **CONFIRMED (by code)** | `clean_string` (`metrics.py:118-126`) has no FM strip; whisker `CLAUDE.md` admits it. The 0.31 nid is persona-specific; mechanism holds. |
| 06-E3 | rapidfuzz↔GPL parity = frozen literals, not full-corpus re-golden (MED) | **CONFIRMED** | `test_edit_distance_parity.py` baked vectors; no 382-paper diff committed. |
| 06-E4 | Whole-doc oracle NID vs block NID diverge on empty-after-normalize blocks (MED) | **CONFIRMED (by code)** | `match.py:155-158` drops empty-normalized blocks; `block_metrics` returns `nid=0.0` when no matches (`match.py:257-258`); oracle uses whole-doc `text_nid` (`score.py:212`). |
| 06-E5 | `_ned` duplicates `normalized_edit_distance` (LOW) | **CONFIRMED** | `match.py:100-107` vs `metrics.py:64-78`; blocks pre-normalized so no score drift. |
| 06-E6 | CJK kept, other non-Latin/emoji stripped (LOW) | **CONFIRMED** | `metrics.py:115` `[^\w\u4e00-\u9fff]`. |
| 06-E7 | Redundant whitespace collapse in `text_nid` (LOW) | **CONFIRMED** | `metrics.py:84-85, 350`; harmless. |
| 10-TC1 | `REGION_SOFT_COUNT=1` single largest verdict distorter, no external citation (CRITICAL) | **CONFIRMED** | `constants.py:43-47` (in-spec rationale only); `score.py:164-166`; 186/205 review (§3a). |
| 10-TC2 | `REF_NID_ADVISORY_EDGE=0.85` sits below corpus mean (HIGH) | **PARTIALLY-CONFIRMED** | Edge + provenance confirmed (`constants.py:85-87`); mean 0.836 is baseline §3b. |
| 10-TC3 | `DRIFT_SOFT_EDGE=0.10` no repo citation, trips 88 (HIGH) | **CONFIRMED (by code); count from baseline** | `constants.py:40-41` has no external-provenance comment (unlike the unigram block); `score.py:168-169`; 88 from §3a. |
| 10-TC4 | UNIGRAM band misfits fail side: 3/382 vs 9 heading (HIGH) | **CONFIRMED** | `constants.py:34-38`; `score.py:156-162`; §3a/b. |
| 10-TC5 | Bench/guard floors inert on the only operational path (MED) | **CONFIRMED** | Corpus lanes error (§4); only `_decide`+oracle run on real data. |
| 10-TC6 | `BLOCK_LOCK_NED=0.25` documented verbatim but dead code (MED) | **CONFIRMED** | Grep over `packages/whisker/src`: only `constants.py:117` defines it; `match.py` uses only `BLOCK_ACCEPT_NED`/`BLOCK_FUZZY_RESCUE_NED` (`165-198`). |
| 10-TC7 | `GUARD_AXIS_SLACK=0.02` vs `BENCH_REGRESSION_SLACK=0.03` inconsistent (MED) | **CONFIRMED (inconsistency); impact unproven** | `constants.py:90, 103`. "Too tight/too loose" is unvalidated speculation; the numeric mismatch and unfitted status are real. |
| 10-TC8 | `QA_SCORE_SOFT_EDGE=70` mirrors tomd, internal not external calibration (LOW) | **CONFIRMED** | `constants.py:49-51`; `score.py:170-171`. |
| 20-L1 | `normalized_text` destroys superscript/operator structure (CRITICAL) | **CONFIRMED** | Runtime `$E = mc^2$`→`Emc2`, `$x^2$`→`x2`, `$\frac{a}{b}$`→`ab` (`metrics.py:140, 314-340`). |
| 20-L2 | Lane 3 `math` facts built but 0/382 operational (CRITICAL) | **CONFIRMED** | Corpus has only `EXAMPLE.facts.jsonl` (§4); facts lane errors with no staged candidate. |
| 20-L3 | False-pass vectors: sqrt/frac/matrix collapse identical (HIGH) | **CONFIRMED (stronger than stated)** | Runtime `text_nid(norm('$\sqrt{x}$'),norm('$x$'))=1.0`; `frac` vs `a/b`=1.0; matrix-pair (skipped fold) identical. Persona's "nid 0.300-0.308" for sqrt/frac is muddled; bare-token nid is **1.0**. |
| 20-L4 | Display `\[..\]` and plain `$..$` without `^_` bypass pylatexenc (HIGH) | **CONFIRMED (by code)** | `_INLINE_REG` = `$..$`/`\(..\)` only (`metrics.py:140`); fold gate requires `\`/`^`/`_` (`metrics.py:322`). |
| 20-L5 | `content_recall`/`unigram_coverage` still miss structural math (HIGH) | **CONFIRMED** | Runtime `content_tokens('$\sqrt{x}$')=['x'] == content_tokens('$x$')=['x']` (`metrics.py:358-369`). sqrt-drop invisible at token level too. |
| 20-L6 | `present` facts share blind spot; only `math` uses `_math_surface` (MED) | **CONFIRMED (by code)** | `facts.py` math vs present paths; not re-run. |
| 20-L7 | Unicode vs LaTeX superscript disagree (`x^2` vs `x²`) (MED) | **CONFIRMED; persona number wrong** | Runtime `text_nid`=**0.5** (1 sub / len 2), NOT the persona's 0.200. Qualitative point (< 0.85, advisory fires) holds. |
| 20-L8 | Unit tests prove the primitive, not corpus math coverage (LOW) | **CONFIRMED** | 353 green ≠ WG21 math facts (§2, §4). |

## Persona errors / overstatements

1. **Persona 02 (Calibration Statistician), C5 — the Youden-J claim is REFUTED.**
   It states the Youden fallback "can silently violate the advertised FPR
   ceiling when no point is feasible." That cannot happen: `_candidate_thresholds`
   includes `min(values)`, at which `value < threshold` flags nothing →
   `fp=0, fpr=0` (`calibrate.py:124-147, 137-147`). `fpr=0 <= target_fpr` for any
   `target_fpr in [0,1]`, so `feasible` is never empty and the
   `else` Youden branch (`calibrate.py:188-190`) is **unreachable dead code**.
   Runtime confirms it across bad>good, target_fpr=0.0, and fully-interleaved
   inputs (always `method=max_tpr_at_fpr`). The *real* defect is the opposite and
   arguably worse: on hard/inverted label sets `calibrate` silently returns a
   degenerate "flag nothing" edge (`tpr=0`) with no warning, so a naive operator
   could promote a useless edge. Persona 02 inverted the failure mode.

2. **Persona 20 (Math), L7 — wrong magnitude.** `text_nid('$x^2$','x²')` is
   **0.5**, not 0.200 (`metrics.py`: `x2` vs `x²`, 1 substitution / max-len 2).
   L3's "sqrt/fraction … nid 0.300-0.308" is also muddled: with no surrounding
   context both sides normalize identically and nid is **1.0** (the false-pass is
   stronger, not weaker, than the persona reported). Directional findings stand;
   the cited numbers do not.

3. **Persona 01 (Metrologist), M3 — borrowed file:line.** The `unigram_coverage =
   multiset recall` construct is correct and confirmed at runtime, but the cited
   `check_content.py:621-624` is a *tomd* location I did not verify; whisker only
   consumes `content.unigram_coverage` (`score.py:227`). Use the construct, not
   that line ref, as the evidence.

4. **Corpus-distribution numbers are baseline-sourced, not re-derived.** Every
   persona leans on §3 counts (186 regions, 147 ref_nid<0.85, mean 0.836, 88
   drift, 3/382 unigram fails). None re-ran `--all`; neither did I (slow + needs
   the oracle). I independently re-confirmed the *mechanisms* that generate them
   and one concrete instance (`P3941R2` fail). Treat the aggregate counts as
   "Opus baseline evidence," not as persona-verified.

## My independent verdict (+ confidence)

**Verdict: usable-with-conditions. Confidence: HIGH.**

Split the layer cleanly, because the personas are right that it is two different
things wearing one name:

- **Measurement kernels are trustworthy as measurements.** `teds` is a faithful
  structural port (lxml→APTED, correct denominator, th→td/thead-strip preprocess);
  `text_nid`/`normalized_edit_distance` are the OmniDocBench NED on rapidfuzz;
  `mhs` and `content_recall` are deterministic and sensibly defined; the
  structural gates are well-formed. These compute exactly what they claim, and
  the code is honestly documented (`PROVISIONAL` banners, advisory demotions,
  null-eligibility). Not garbage.

- **The verdict/calibration layer is NOT a calibrated classifier and must not be
  read as one.** No threshold has a measured TPR/FPR on this corpus; the one
  tunable the calibrator touches (`unigram_coverage`) drives ~0.8% of fails while
  the actual fail driver is heading typography and the actual review driver is a
  benign single-region flag; the text axis is provably blind to formula
  structure, table-cell permutation, reading order, and symbol-only content
  (confirmed false-passes); and the headline `ovr=` operators eyeball mixes
  axes (teds/mhs) the spec itself says carry no signal against the oracle. The
  designed mitigation (Lane 3 math facts) runs on 0/382 papers.

Net: trust whisker as a **deterministic advisory triage with a human in the
loop** and as a regression detector once a baseline exists. Do **not** quote its
pass/review/fail as a calibrated quality gate, do not treat `review` as an
ordinal of "how broken," and do not treat a `pass` as evidence that math/tables/
order survived. "garbage" is wrong (kernels sound, honestly labeled); unqualified
"usable" is wrong (zero known operating characteristics).

## Top-3 issues for the final report

1. **CRITICAL — Calibration is absent AND the calibrator structurally cannot fix
   the dominant verdict drivers.** Zero measured TPR/FPR anywhere
   (`constants.py:11-15`, no labels). `whisker calibrate` fits only
   `unigram_coverage` (`__main__.py:829-838`), which gates ~3/14 hard fails and
   ~0.8% of papers, while the real drivers — `heading_monotone` (9/14 fails) and
   `REGION_SOFT_COUNT=1` (186/205 reviews) — sit outside its objective. Compounding
   it, the documented Youden-J fallback (`calibrate.py:188-190`) is unreachable
   dead code (flag-nothing min threshold is always feasible at fpr=0), so on a
   hard label set the fit silently returns a degenerate `tpr=0` edge. A "5%/10%
   FPR" claim is not yet supportable for any gate.

2. **HIGH (false-fail) — `heading_monotone` hard-fails faithful conversions on
   typography.** `gates.py:96-112` FAILS on any H{n}→H{n+2} jump regardless of
   content. Runtime `P3941R2`: `uni=0.999, cov=0.997, drift=0.002, qa=95` → `fail`
   solely on `H2 -> H4`. This is the majority of corpus fails (9/14). A content-QA
   gate that hard-fails on heading numbering is a construct error; demote to soft
   or scope it.

3. **HIGH (false-pass) — the text axis is blind to math/order/symbol content, and
   the designed mitigation does not run.** `normalized_text` collapses
   `$\sqrt{x}$`→`x`, `$\frac{a}{b}$`→`ab`, symbol-only→`''` (runtime `text_nid`=
   1.0 in each case); `unigram_coverage` is multiset recall (sqrt-drop invisible at
   the token level: `content_tokens` both `['x']`); a multiset-preserving table-cell
   permutation passes `_decide` with `uni=1.0`. Lane 3 `math` facts (the intended
   fix) are enforced on 0/382 papers. So formula corruption and cell-swap defects
   can clear the only operational gate; `ref_overall=(nid+teds+mhs)/3`
   (`score.py:215`) further masks this by averaging non-signal axes into the
   displayed `ovr=`.
